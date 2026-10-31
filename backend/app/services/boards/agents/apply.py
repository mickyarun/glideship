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
boards stays canceled. Runs earn no XP or SP.

The Garden hears ``agent_activity:<org_id>`` like it does for BUD agents,
naming the card only when the board is visible to the whole org.
"""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_skill import AgentSkill
from app.models.board import Board
from app.models.board_agent import ACTIVE_RUN_STATUSES, BoardAgentRunStatus, BoardCardAgentRun
from app.models.board_card import BoardCard
from app.models.board_enums import BoardCardEventType, BoardVisibility
from app.models.notification import NotificationType
from app.repositories.board_agent_run import BoardCardAgentRunRepository
from app.repositories.board_card_links import BoardCardLinkRepository
from app.services.boards.agents.runs import queue_run_event, settle
from app.services.boards.card_notify import send, stage_board_card_notice
from app.services.boards.events import record_event
from app.services.boards.reads import card_key
from app.services.event_bus import publish
from app.services.notifications import NotificationCategory

_GARDEN_STATUS = {
    "skill_invoked": "in_progress",
    "skill_completed": "completed",
    "skill_failed": "failed",
}


@dataclass(frozen=True)
class RunRefs:
    """The rows a run's end touches."""

    board: Board
    card: BoardCard
    run: BoardCardAgentRun
    skill: AgentSkill


def garden_event(refs: RunRefs, event_type: str) -> None:
    """Tell the Garden a board agent started, finished or failed."""
    open_board = refs.board.visibility is BoardVisibility.ORG
    publish(
        f"agent_activity:{refs.card.org_id}",
        {
            "event_type": event_type,
            "status": _GARDEN_STATUS[event_type],
            "message": f"Skill '{refs.skill.skill_slug}' on a board card",
            "skill_slug": refs.skill.skill_slug,
            "actor_name": refs.skill.skill_slug,
            "task_id": str(refs.run.id),
            "repo_name": None,
            "bud_number": None,
            "bud_title": None,
            "card_key": card_key(refs.board.key, refs.card.number) if open_board else None,
            "impacted_repo_names": [],
            "created_at": "",
        },
    )


async def _settle(
    db: AsyncSession,
    refs: RunRefs,
    status: BoardAgentRunStatus,
    *,
    error: str | None = None,
    summary: dict[str, Any] | None = None,
) -> bool:
    """Settle the run if it's still active and record it on the card; False when it wasn't."""
    run = refs.run
    await BoardCardAgentRunRepository(db, org_id=run.org_id).lock(run)
    if run.status not in ACTIVE_RUN_STATUSES:
        return False
    settle(run, status, error=error)
    run.result_summary = summary
    detail: dict[str, Any] = {
        "run_id": str(run.id),
        "skill_id": str(refs.skill.id),
        "skill": refs.skill.name,
        "status": status.value,
        **(summary or {}),
    }
    if error is not None:
        detail["error"] = run.error_message
    await record_event(db, refs.card, BoardCardEventType.AI_RUN, actor_id=None, detail=detail)
    await db.flush()
    queue_run_event(db, refs.board.id, run)
    return True


async def _assignees(db: AsyncSession, card: BoardCard) -> set[uuid.UUID]:
    return await BoardCardLinkRepository(db, org_id=card.org_id).assignee_ids(card.id)


async def finish_succeeded(db: AsyncSession, refs: RunRefs, summary: dict[str, Any]) -> bool:
    """Mark the run completed, tell the assignees a draft waits, and commit."""
    if not await _settle(db, refs, BoardAgentRunStatus.COMPLETED, summary=summary):
        await db.commit()
        return False
    notice = await stage_board_card_notice(
        db,
        refs.board,
        refs.card,
        await _assignees(db, refs.card),
        kind=NotificationType.BOARD_AI_DRAFT,
        category=NotificationCategory.BOARD_CARDS,
        title="An AI draft is ready to review",
        lead=f"{refs.skill.name} drafted a document for",
    )
    await db.commit()
    send(notice)
    return True


async def finish_failed(db: AsyncSession, refs: RunRefs, error: str) -> bool:
    """Mark the run failed (the card is untouched), tell the assignees, and commit."""
    if not await _settle(db, refs, BoardAgentRunStatus.FAILED, error=error):
        await db.commit()
        return False
    notice = await stage_board_card_notice(
        db,
        refs.board,
        refs.card,
        await _assignees(db, refs.card),
        kind=NotificationType.BOARD_AI_FAILED,
        category=NotificationCategory.BOARD_CARDS,
        title="An AI run failed",
        lead=f"{refs.skill.name} couldn't finish its run on",
    )
    await db.commit()
    send(notice)
    garden_event(refs, "skill_failed")
    return True


async def settle_canceled(db: AsyncSession, refs: RunRefs, reason: str) -> bool:
    """Mark a still-active run canceled and record it on the card; the caller commits."""
    return await _settle(db, refs, BoardAgentRunStatus.CANCELED, error=reason)


async def finish_canceled(db: AsyncSession, refs: RunRefs, reason: str) -> None:
    """Mark a still-active run canceled, with no notice, and commit."""
    await settle_canceled(db, refs, reason)
    await db.commit()
