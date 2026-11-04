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

"""What goes in a daily follow-ups DM besides cards: BUD targets and last comments.

Cards come from :class:`app.repositories.board_due.BoardDueRepository`.
BUDs have no due date of their own; their current phase's target date
(``current_phase_deadline``, a forecast or a manual override) stands in.
"""

import uuid
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_card_detail import BoardCardComment
from app.models.bud import BUDDocument, BUDStatus
from app.models.user import OrgToUser, User
from app.repositories.membership_predicates import membership_holds

FINISHED_BUD_STATUSES = (BUDStatus.CLOSED, BUDStatus.DISCARDED)


@dataclass(frozen=True)
class TargetBud:
    """An open BUD whose current phase target falls before the cutoff."""

    user_id: uuid.UUID
    bud_number: int
    title: str
    status: BUDStatus
    target_at: datetime


@dataclass(frozen=True)
class LastComment:
    """The newest live comment on a card."""

    author: str
    body: str
    created_at: datetime


class FollowupItemsRepository:
    """Follow-ups content in one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        """Initialize the repository."""
        self._db = db
        self._org = org_id

    async def bud_targets(
        self, user_ids: Collection[uuid.UUID], before: datetime, *, permission: str
    ) -> list[TargetBud]:
        """Open BUDs assigned to ``user_ids`` whose phase target is before ``before``.

        Only for assignees whose role still grants ``permission`` (the one
        that opens BUDs), so nobody is sent a BUD they can't open.
        """
        if not user_ids:
            return []
        rows = await self._db.execute(
            select(
                BUDDocument.assignee_id,
                BUDDocument.bud_number,
                BUDDocument.title,
                BUDDocument.status,
                BUDDocument.current_phase_deadline,
            )
            .join(
                OrgToUser,
                and_(
                    OrgToUser.user_id == BUDDocument.assignee_id,
                    OrgToUser.org_id == self._org,
                ),
            )
            .where(
                membership_holds(permission),
                BUDDocument.org_id == self._org,
                BUDDocument.assignee_id.in_(list(user_ids)),
                BUDDocument.status.not_in(FINISHED_BUD_STATUSES),
                BUDDocument.current_phase_deadline.is_not(None),
                BUDDocument.current_phase_deadline < before,
            )
            .order_by(BUDDocument.current_phase_deadline, BUDDocument.bud_number)
        )
        return [TargetBud(*row) for row in rows.all()]

    async def last_card_comments(
        self, card_ids: Collection[uuid.UUID]
    ) -> dict[uuid.UUID, LastComment]:
        """Each card's newest comment that isn't deleted (one query)."""
        if not card_ids:
            return {}
        author = func.coalesce(User.name, BoardCardComment.author_label, "Someone")
        rows = await self._db.execute(
            select(
                BoardCardComment.card_id,
                author,
                BoardCardComment.body,
                BoardCardComment.created_at,
            )
            .outerjoin(User, User.id == BoardCardComment.author_id)
            .where(
                BoardCardComment.org_id == self._org,
                BoardCardComment.card_id.in_(list(card_ids)),
                BoardCardComment.deleted_at.is_(None),
            )
            .distinct(BoardCardComment.card_id)
            .order_by(BoardCardComment.card_id, BoardCardComment.created_at.desc())
        )
        return {row[0]: LastComment(row[1], row[2], row[3]) for row in rows.all()}
