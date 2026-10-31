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

"""How a card run's end lands: the run row, the card's history, live events and notices.

A finished run records an ``ai_run`` event on the card and announces
``agent_run_updated`` on its board; the card's assignees hear that a draft is
waiting (``board_ai_draft``) or that the run failed (``board_ai_failed``),
after the commit. A failed run leaves the card as it was; Retry starts a new
run. Only a run still active is settled, so a run canceled by a move between
boards stays canceled. A run whose skill was deleted is settled the same way,
naming no skill. Runs earn no XP or SP. The Garden hears about the run from
its job (:mod:`.garden`), which knows whether it ever told it the run began.
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_agent import (
    ACTIVE_RUN_STATUSES,
    BoardAgentRunErrorCode,
    BoardAgentRunStatus,
)
from app.models.board_card import BoardCard
from app.models.board_enums import BoardCardEventType
from app.models.notification import NotificationType
from app.repositories.board_agent_run import BoardCardAgentRunRepository
from app.repositories.board_card_links import BoardCardLinkRepository
from app.services.boards.agents.refs import RunRow
from app.services.boards.agents.runs import queue_run_event, settle
from app.services.boards.card_notify import send, stage_board_card_notice
from app.services.boards.events import record_event
from app.services.notifications import NotificationCategory

# Who the notices name when the run's skill was deleted.
UNNAMED_AGENT = "An AI agent"


async def _settle(
    db: AsyncSession,
    row: RunRow,
    status: BoardAgentRunStatus,
    *,
    error: str | None = None,
    code: BoardAgentRunErrorCode | None = None,
    summary: dict[str, Any] | None = None,
    actor_id: uuid.UUID | None = None,
) -> bool:
    """Settle the run if it's still active and record it on the card; False when it wasn't."""
    run = row.run
    await BoardCardAgentRunRepository(db, org_id=run.org_id).lock(run)
    if run.status not in ACTIVE_RUN_STATUSES:
        return False
    settle(run, status, error=error, code=code)
    run.result_summary = summary
    detail: dict[str, Any] = {
        "run_id": str(run.id),
        "skill_id": None if row.skill is None else str(row.skill.id),
        "skill": None if row.skill is None else row.skill.name,
        "status": status.value,
        **(summary or {}),
    }
    if error is not None:
        detail["error"] = run.error_message
    if code is not None:
        detail["error_code"] = code.value
    await record_event(db, row.card, BoardCardEventType.AI_RUN, actor_id=actor_id, detail=detail)
    await db.flush()
    await queue_run_event(db, row.board.id, run, actor_id=actor_id)
    return True


async def _assignees(db: AsyncSession, card: BoardCard) -> set[uuid.UUID]:
    return await BoardCardLinkRepository(db, org_id=card.org_id).assignee_ids(card.id)


def _agent_name(row: RunRow) -> str:
    return UNNAMED_AGENT if row.skill is None else row.skill.name


async def finish_succeeded(db: AsyncSession, row: RunRow, summary: dict[str, Any]) -> bool:
    """Mark the run completed, tell the assignees a draft waits, and commit."""
    if not await _settle(db, row, BoardAgentRunStatus.COMPLETED, summary=summary):
        await db.commit()
        return False
    notice = await stage_board_card_notice(
        db,
        row.board,
        row.card,
        await _assignees(db, row.card),
        kind=NotificationType.BOARD_AI_DRAFT,
        category=NotificationCategory.BOARD_CARDS,
        title="An AI draft is ready to review",
        lead=f"{_agent_name(row)} drafted a document for",
    )
    await db.commit()
    send(notice)
    return True


async def finish_failed(
    db: AsyncSession, row: RunRow, error: str, code: BoardAgentRunErrorCode
) -> bool:
    """Mark the run failed (the card is untouched), tell the assignees, and commit."""
    if not await _settle(db, row, BoardAgentRunStatus.FAILED, error=error, code=code):
        await db.commit()
        return False
    notice = await stage_board_card_notice(
        db,
        row.board,
        row.card,
        await _assignees(db, row.card),
        kind=NotificationType.BOARD_AI_FAILED,
        category=NotificationCategory.BOARD_CARDS,
        title="An AI run failed",
        lead=f"{_agent_name(row)} couldn't finish its run on",
    )
    await db.commit()
    send(notice)
    return True


async def settle_canceled(
    db: AsyncSession,
    row: RunRow,
    reason: str,
    code: BoardAgentRunErrorCode = BoardAgentRunErrorCode.CANCELED,
    *,
    actor_id: uuid.UUID | None = None,
) -> bool:
    """Mark a still-active run canceled and record it on the card; the caller commits."""
    return await _settle(
        db, row, BoardAgentRunStatus.CANCELED, error=reason, code=code, actor_id=actor_id
    )


async def finish_canceled(
    db: AsyncSession,
    row: RunRow,
    reason: str,
    code: BoardAgentRunErrorCode = BoardAgentRunErrorCode.CANCELED,
) -> bool:
    """Mark a still-active run canceled, with no notice, and commit; False when it wasn't."""
    settled = await settle_canceled(db, row, reason, code)
    await db.commit()
    return settled
