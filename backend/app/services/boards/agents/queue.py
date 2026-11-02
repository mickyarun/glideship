# Copyright 2025-2026 Arun Rajkumar
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Enqueueing a committed run's job, and what happens when the queue is full.

The in-memory queue is bounded. A run it can't take is marked failed with
:data:`QUEUE_FULL` (so Retry starts it again) like any failed run: an
``ai_run`` event on the card, ``agent_run_updated`` on its board and a notice
to the card's assignees. From the Run button that is a 503 with ``Retry-After``;
for a run an entry started, the move that started it has already committed,
so the run is failed on its own session in the background.
"""

import asyncio
import uuid
from collections.abc import Callable

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.board_agent import BoardAgentRunErrorCode, BoardCardAgentRun
from app.repositories.board_agent_run import BoardCardAgentRunRepository
from app.schemas.boards.agent import AgentRunAccepted, BoardAgentRunPayload
from app.services.boards.agents.apply import finish_failed
from app.services.boards.agents.loading import run_row
from app.services.boards.agents.runs import run_read
from app.services.boards.errors import BoardBusyError
from app.services.job_queue import JOB_BOARD_AGENT_RUN, create_job_with_id

logger = structlog.get_logger(__name__)

QUEUE_FULL = "Too many agent runs are queued right now. Try again in a minute."

# Background failures in flight, held so they aren't garbage-collected.
_pending: set[asyncio.Task[None]] = set()


def _enqueue(run: BoardCardAgentRun) -> bool:
    """Put the run's job on the queue; False when it can't take it."""
    assert run.job_id is not None  # every run is claimed with a job id
    payload = BoardAgentRunPayload(org_id=run.org_id, run_id=run.id)
    triggered_by = None if run.triggered_by is None else str(run.triggered_by)
    try:
        create_job_with_id(
            run.job_id,
            JOB_BOARD_AGENT_RUN,
            payload=payload.model_dump(mode="json"),
            user_id=triggered_by,
        )
    except (asyncio.QueueFull, RuntimeError):
        # RuntimeError: the queue is shutting down and takes no more jobs.
        logger.warning("board_agent_run_queue_full", run_id=str(run.id))
        return False
    return True


async def _fail_queued(db: AsyncSession, run: BoardCardAgentRun) -> None:
    """Fail a run the queue couldn't take, as any failed run is (commits)."""
    row = await run_row(db, run)
    if row is not None:
        await finish_failed(db, row, QUEUE_FULL, BoardAgentRunErrorCode.QUEUE_FULL)


async def enqueue_now(db: AsyncSession, run: BoardCardAgentRun) -> AgentRunAccepted:
    """Enqueue a run the caller just committed; the 202 body.

    Raises:
        BoardBusyError: The queue is full; the run is now failed (503).
    """
    if not _enqueue(run):
        await _fail_queued(db, run)
        wait = settings.boards.agent_busy_retry_after_seconds
        raise BoardBusyError(QUEUE_FULL, retry_after_seconds=wait)
    assert run.job_id is not None
    # Just queued: there is no error to show anyone yet.
    return AgentRunAccepted(job_id=run.job_id, run=run_read(run, show_error=False))


def enqueue_after_commit(run: BoardCardAgentRun) -> Callable[[], None]:
    """A commit callback that enqueues ``run``, failing it in the background if it can't."""
    org_id, run_id = run.org_id, run.id

    def callback() -> None:
        if _enqueue(run):
            return
        task = asyncio.get_running_loop().create_task(_fail_in_background(org_id, run_id))
        _pending.add(task)
        task.add_done_callback(_pending.discard)

    return callback


async def _fail_in_background(org_id: uuid.UUID, run_id: uuid.UUID) -> None:
    try:
        async with AsyncSessionLocal() as db:
            run = await BoardCardAgentRunRepository(db, org_id=org_id).get_by_id(run_id)
            if run is not None:
                await _fail_queued(db, run)
    except Exception:
        logger.exception("board_agent_run_fail_queued_failed", run_id=str(run_id))
