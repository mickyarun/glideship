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

"""Board-card and HR facts for check-ins.

Board cards: a card counts when its stage entered a done stage in the
period and it is still done now. ``completed_at`` alone can't be used: it
is also set when a card is canceled and cleared when it reopens. Archived
cards and cards on archived boards still count, and every current
assignee gets credit.

HR facts come only from rows where the person is the actor, and say what
the work was, never whose records were touched.
"""

import uuid
from collections.abc import Collection
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_enums import FactSource
from app.models.board import Board, BoardStage
from app.models.board_card import BoardCard, BoardCardAssignee
from app.models.board_card_detail import BoardCardEvent
from app.models.board_enums import BoardStageCategory
from app.models.employee_audit_event import EmployeeAuditAction, EmployeeAuditEvent
from app.models.leave_config_event import LeaveConfigAction, LeaveConfigEvent
from app.models.leave_policy import LeavePolicy
from app.repositories.board_access import BoardAccessRepository, PermissionChecker
from app.repositories.work_facts import FactRow

HR_ACTION_WORDS: dict[LeaveConfigAction, str] = {
    LeaveConfigAction.POLICY_CREATED: "Set up the leave policy",
    LeaveConfigAction.POLICY_UPDATED: "Updated the leave policy",
    LeaveConfigAction.POLICY_MADE_DEFAULT: "Made the default leave policy",
    LeaveConfigAction.POLICY_DELETED: "Retired a leave policy",
    LeaveConfigAction.TYPE_CREATED: "Added a leave type to",
    LeaveConfigAction.TYPE_UPDATED: "Updated a leave type in",
    LeaveConfigAction.EMPLOYEES_ASSIGNED: "Moved people onto",
    LeaveConfigAction.LIBRARY_TYPE_CREATED: "Added a leave type to the library",
    LeaveConfigAction.LIBRARY_TYPE_UPDATED: "Updated a leave type in the library",
    LeaveConfigAction.LIBRARY_TYPE_DELETED: "Removed a leave type from the library",
}


class OtherFactsRepository:
    """Board and HR facts within one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        """Initialize the repository."""
        self._db = db
        self._org = org_id

    async def board_cards(
        self, users: Collection[uuid.UUID], start: datetime, end: datetime
    ) -> list[FactRow]:
        """Cards assigned to them that reached a done stage in the period and stayed done."""
        done = (
            select(BoardCardEvent.card_id, func.max(BoardCardEvent.created_at).label("at"))
            .where(
                BoardCardEvent.org_id == self._org,
                BoardCardEvent.to_category == BoardStageCategory.DONE,
                BoardCardEvent.created_at >= start,
                BoardCardEvent.created_at < end,
            )
            .group_by(BoardCardEvent.card_id)
            .subquery()
        )
        stmt = (
            select(BoardCard.id, Board.key, BoardCard.number, BoardCard.title, done.c.at, Board.id)
            .join(done, done.c.card_id == BoardCard.id)
            .join(Board, Board.id == BoardCard.board_id)
            .join(BoardStage, BoardStage.id == BoardCard.stage_id)
            .join(BoardCardAssignee, BoardCardAssignee.card_id == BoardCard.id)
            .where(
                BoardCard.org_id == self._org,
                BoardStage.category == BoardStageCategory.DONE,
                BoardCardAssignee.user_id.in_(users),
            )
            .distinct()
        )
        rows = (await self._db.execute(stmt)).tuples().all()
        return [
            FactRow(
                FactSource.BOARD_CARDS,
                str(card_id),
                f"{key}-{number}",
                title,
                f"/boards/{key}/cards/{number}",
                at,
                "done",
                board_id,
            )
            for card_id, key, number, title, at, board_id in rows
        ]

    async def hr_records(
        self, users: Collection[uuid.UUID], start: datetime, end: datetime
    ) -> list[FactRow]:
        """Leave setup they did, and a count of employee documents they uploaded."""
        config = (
            select(
                LeaveConfigEvent.id,
                LeaveConfigEvent.action,
                LeavePolicy.name,
                LeaveConfigEvent.created_at,
            )
            .outerjoin(LeavePolicy, LeavePolicy.id == LeaveConfigEvent.policy_id)
            .where(
                LeaveConfigEvent.org_id == self._org,
                LeaveConfigEvent.actor_id.in_(users),
                LeaveConfigEvent.created_at >= start,
                LeaveConfigEvent.created_at < end,
            )
        )
        events = (await self._db.execute(config)).tuples().all()
        out = [
            FactRow(
                FactSource.HR_RECORDS,
                str(event_id),
                "Leave setup",
                " ".join(filter(None, [HR_ACTION_WORDS[action], policy])),
                "/leave/settings",
                at,
                "set up",
            )
            for event_id, action, policy, at in events
        ]
        docs = select(func.count(), func.max(EmployeeAuditEvent.created_at)).where(
            EmployeeAuditEvent.org_id == self._org,
            EmployeeAuditEvent.actor_id.in_(users),
            EmployeeAuditEvent.action == EmployeeAuditAction.DOCUMENT_UPLOADED,
            EmployeeAuditEvent.created_at >= start,
            EmployeeAuditEvent.created_at < end,
        )
        count, last = (await self._db.execute(docs)).one()
        if count:
            out.append(
                FactRow(
                    FactSource.HR_RECORDS,
                    f"documents:{start:%Y-%m-%d}",
                    "Documents",
                    f"Uploaded {count} employee document{'s' if count != 1 else ''}",
                    "/people",
                    last,
                    "uploaded",
                )
            )
        return out


async def readable_boards(
    db: AsyncSession,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    perms: PermissionChecker,
    board_ids: Collection[uuid.UUID],
) -> set[uuid.UUID]:
    """Which of these boards the viewer may open, archived ones included."""
    if not board_ids:
        return set()
    roles = BoardAccessRepository(db, org_id=org_id).role_subquery(user_id, perms)
    stmt = select(roles.c.board_id).where(roles.c.board_id.in_(board_ids))
    return set((await db.execute(stmt)).scalars().all())
