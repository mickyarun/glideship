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

"""A card's agent runs: reading them, announcing changes, settling and canceling them.

A stale run (past its deadline plus a grace, :mod:`app.repositories.board_agent_run_sweep`)
doesn't hold the card: starting a new run fails it first, and its job is
stopped after the commit.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.board_agent import (
    BoardAgentRunErrorCode,
    BoardAgentRunStatus,
    BoardCardAgentRun,
)
from app.models.board_card import BoardCard
from app.repositories.agent_skill import AgentSkillRepository
from app.repositories.board_agent_run import BoardCardAgentRunRepository
from app.repositories.board_agent_run_sweep import STALE, fail_stale_runs
from app.schemas.boards.agent import AgentRunRead
from app.services.after_commit import call_after_commit
from app.services.boards.access import CardAccess
from app.services.boards.constants import BoardAction
from app.services.boards.live import BoardChanges, BoardSocketEvent
from app.services.job_queue import cancel_job

# What a run moved off its board says, for the run row and the job.
MOVED_BOARD = "The card moved to another board, so its agent run stopped."
# A stopped run's job reason when the run row names none.
RUN_STOPPED = "This agent run was stopped."


def stop_reason(run: BoardCardAgentRun) -> str:
    """Why a run that is no longer going stopped, for its job."""
    return run.error_message or RUN_STOPPED


def run_read(run: BoardCardAgentRun, *, show_error: bool) -> AgentRunRead:
    """One run for the API: ``error_code`` always, ``error_message`` only when ``show_error``.

    The raw message can carry provider output, so only board admins read it;
    everyone else gets the code, which the card's panel turns into words.
    """
    read = AgentRunRead.model_validate(run)
    return read if show_error else read.model_copy(update={"error_message": None})


def shows_run_errors(target: CardAccess) -> bool:
    """Whether the caller reads runs' raw error messages (board admins)."""
    return target.access.may(BoardAction.CONFIGURE_AGENTS)


def run_json(run: BoardCardAgentRun) -> dict[str, object]:
    """One run as a socket payload: everyone on the board hears it, so no raw error."""
    return run_read(run, show_error=False).model_dump(mode="json")


async def queue_run_event(
    db: AsyncSession,
    board_id: uuid.UUID,
    run: BoardCardAgentRun,
    *,
    actor_id: uuid.UUID | None = None,
    origin: str | None = None,
) -> None:
    """Queue ``agent_run_updated`` with the run as it is now, for when ``db`` commits.

    ``skill_name`` names the run's skill (null once it was deleted), so a
    tile's chip can say who is working without another read.
    """
    skill = (
        await AgentSkillRepository(db, org_id=run.org_id).get_by_id(run.skill_id)
        if run.skill_id
        else None
    )
    changes = BoardChanges(board_id, actor_id, origin)
    changes.emit(
        BoardSocketEvent.AGENT_RUN_UPDATED,
        card_id=str(run.card_id),
        run=run_json(run),
        skill_name=None if skill is None else skill.name,
    )
    changes.queue(db)


async def clear_stale(db: AsyncSession, board_id: uuid.UUID, card: BoardCard) -> None:
    """Fail the card's active run if it is stale, so a new one can start; the caller commits."""
    cfg = settings.boards
    stale = await fail_stale_runs(
        db,
        timeout_seconds=cfg.agent_timeout_seconds,
        grace_seconds=cfg.agent_stale_grace_seconds,
        org_id=card.org_id,
        card_id=card.id,
    )
    for run, _board_id in stale:
        await queue_run_event(db, board_id, run)
        stop_job_after_commit(db, run, STALE)


def settle(
    run: BoardCardAgentRun,
    status: BoardAgentRunStatus,
    *,
    error: str | None = None,
    code: BoardAgentRunErrorCode | None = None,
) -> None:
    """Give the run its final status, why it ended without a draft, and when it finished."""
    run.status = status
    run.error_message = None if error is None else error[:500]
    run.error_code = code
    run.finished_at = datetime.now(UTC)


async def card_runs(
    db: AsyncSession, target: CardAccess
) -> tuple[list[AgentRunRead], AgentRunRead | None]:
    """The card's latest runs, and the active one."""
    repo = BoardCardAgentRunRepository(db, org_id=target.access.org_id)
    recent = await repo.recent_for_card(target.card.id, settings.boards.agent_runs_page_size)
    active = await repo.active_for_card(target.card.id)
    show = shows_run_errors(target)
    return (
        [run_read(r, show_error=show) for r in recent],
        None if active is None else run_read(active, show_error=show),
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
    settle(run, BoardAgentRunStatus.CANCELED, error=reason, code=BoardAgentRunErrorCode.CANCELED)
    await db.flush()
    await queue_run_event(db, card.board_id, run)
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
