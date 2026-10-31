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

"""A card's agent runs: reading them, announcing changes, settling and canceling them."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.board_agent import BoardAgentRunStatus, BoardCardAgentRun
from app.models.board_card import BoardCard
from app.repositories.board_agent_run import BoardCardAgentRunRepository
from app.schemas.boards.agent import AgentRunRead
from app.services.after_commit import call_after_commit
from app.services.boards.access import CardAccess
from app.services.boards.live import BoardChanges, BoardSocketEvent
from app.services.job_queue import cancel_job

# What a run moved off its board says, for the run row and the job.
MOVED_BOARD = "The card moved to another board, so its agent run stopped."


def run_json(run: BoardCardAgentRun) -> dict[str, object]:
    """One run as a socket payload."""
    return AgentRunRead.model_validate(run).model_dump(mode="json")


def queue_run_event(
    db: AsyncSession,
    board_id: uuid.UUID,
    run: BoardCardAgentRun,
    *,
    actor_id: uuid.UUID | None = None,
    origin: str | None = None,
) -> None:
    """Queue ``agent_run_updated`` with the run as it is now, for when ``db`` commits."""
    changes = BoardChanges(board_id, actor_id, origin)
    changes.emit(BoardSocketEvent.AGENT_RUN_UPDATED, card_id=str(run.card_id), run=run_json(run))
    changes.queue(db)


def settle(
    run: BoardCardAgentRun,
    status: BoardAgentRunStatus,
    *,
    error: str | None = None,
) -> None:
    """Give the run its final status, and when it finished."""
    run.status = status
    run.error_message = None if error is None else error[:500]
    run.finished_at = datetime.now(UTC)


async def card_runs(
    db: AsyncSession, target: CardAccess
) -> tuple[list[AgentRunRead], AgentRunRead | None]:
    """The card's latest runs, and the active one."""
    repo = BoardCardAgentRunRepository(db, org_id=target.access.org_id)
    recent = await repo.recent_for_card(target.card.id, settings.boards.agent_runs_page_size)
    active = await repo.active_for_card(target.card.id)
    return (
        [AgentRunRead.model_validate(r) for r in recent],
        None if active is None else AgentRunRead.model_validate(active),
    )


async def cancel_active_run(
    db: AsyncSession, card: BoardCard, *, reason: str = MOVED_BOARD
) -> BoardCardAgentRun | None:
    """Cancel the card's active run with the request; its job is stopped after the commit.

    The card's board hears ``agent_run_updated``. A job still queued never
    starts; one running is interrupted, and its draft (if any) stays a draft.
    """
    repo = BoardCardAgentRunRepository(db, org_id=card.org_id)
    run = await repo.active_for_card(card.id)
    if run is None:
        return None
    await repo.lock(run)
    if run.status not in (BoardAgentRunStatus.PENDING, BoardAgentRunStatus.RUNNING):
        return None
    settle(run, BoardAgentRunStatus.CANCELED, error=reason)
    await db.flush()
    queue_run_event(db, card.board_id, run)
    stop_job_after_commit(db, run, reason)
    return run


def stop_job_after_commit(db: AsyncSession, run: BoardCardAgentRun, reason: str) -> None:
    """Cancel the run's job once ``db`` commits: a queued one never starts, a running one stops.

    A running job then goes through the executor's cancel path, which finds
    the run already settled and only revokes its token.
    """
    job_id = run.job_id
    if job_id is not None:
        call_after_commit(db, lambda: _stop(job_id, reason))


def _stop(job_id: str, reason: str) -> None:
    cancel_job(job_id, reason=reason)
