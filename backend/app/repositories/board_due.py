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

"""Open cards that are due, per assignee, for the morning due reminders.

Open means: not archived, its due date not ticked done, in a stage that
isn't ``done`` or ``canceled``, on a board that isn't archived. Whether the
assignee may still open the board is checked by the caller with
``BoardAccessRepository.access_pairs``.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import and_, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board import Board, BoardStage
from app.models.board_card import BoardCard, BoardCardAssignee
from app.models.board_enums import COMPLETED_CATEGORIES, BoardStatus
from app.models.digest_claim import DigestClaim, DigestClaimKind
from app.models.leave_policy import LeavePolicy
from app.models.organization import Organization


@dataclass(frozen=True)
class DueOrg:
    """An org with due cards, and what its local time is worked out from."""

    org_id: uuid.UUID
    config: dict[str, Any] | None
    # The default leave policy's timezone, when the org has one.
    policy_timezone: str | None


@dataclass(frozen=True)
class DueCard:
    """One open, due card and one of its assignees."""

    user_id: uuid.UUID
    board_id: uuid.UUID
    board_key: str
    board_name: str
    card_id: uuid.UUID
    number: int
    title: str
    stage_name: str
    due_at: datetime


def _open_due(before: datetime) -> list[Any]:
    return [
        BoardCard.archived_at.is_(None),
        BoardCard.completed_at.is_(None),
        BoardCard.due_at.is_not(None),
        BoardCard.due_at < before,
        BoardCard.due_done.is_(False),
        Board.status == BoardStatus.ACTIVE,
        BoardStage.category.not_in(COMPLETED_CATEGORIES),
    ]


async def orgs_with_due_cards(db: AsyncSession, before: datetime) -> list[DueOrg]:
    """Every org with an open card due before ``before``, with what its zone needs.

    Spans every org: the scheduler's starting point, so it can tell which
    orgs are in their reminder window before opening a session for any.
    """
    has_due = exists(
        select(BoardCard.id)
        .join(Board, Board.id == BoardCard.board_id)
        .join(BoardStage, BoardStage.id == BoardCard.stage_id)
        .join(BoardCardAssignee, BoardCardAssignee.card_id == BoardCard.id)
        .where(BoardCard.org_id == Organization.id, *_open_due(before))
    )
    policy = and_(LeavePolicy.org_id == Organization.id, LeavePolicy.is_default.is_(True))
    rows = await db.execute(
        select(Organization.id, Organization.config, LeavePolicy.timezone)
        .outerjoin(LeavePolicy, policy)
        .where(has_due)
    )
    return [DueOrg(org_id=r[0], config=r[1], policy_timezone=r[2]) for r in rows.all()]


class BoardDueRepository:
    """Due cards in one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        self._db = db
        self._org_id = org_id

    async def due_by_assignee(
        self,
        before: datetime,
        *,
        unclaimed: tuple[DigestClaimKind, date] | None = None,
        user_ids: set[uuid.UUID] | None = None,
    ) -> list[DueCard]:
        """Every open card due before ``before``, once per assignee, soonest first.

        ``unclaimed`` leaves out people who already hold a claim of that
        kind for that day; ``user_ids`` keeps only those people.
        """
        stmt = (
            select(
                BoardCardAssignee.user_id,
                Board.id,
                Board.key,
                Board.name,
                BoardCard.id,
                BoardCard.number,
                BoardCard.title,
                BoardStage.name,
                BoardCard.due_at,
            )
            .join(BoardCardAssignee, BoardCardAssignee.card_id == BoardCard.id)
            .join(Board, Board.id == BoardCard.board_id)
            .join(BoardStage, BoardStage.id == BoardCard.stage_id)
            .where(
                BoardCard.org_id == self._org_id,
                Board.org_id == self._org_id,
                BoardCardAssignee.org_id == self._org_id,
                *_open_due(before),
            )
            .order_by(BoardCard.due_at, Board.key, BoardCard.number)
        )
        if unclaimed is not None:
            kind, day = unclaimed
            claimed = exists().where(
                DigestClaim.org_id == self._org_id,
                DigestClaim.kind == kind,
                DigestClaim.user_id == BoardCardAssignee.user_id,
                DigestClaim.local_date == day,
            )
            stmt = stmt.where(~claimed)
        if user_ids is not None:
            stmt = stmt.where(BoardCardAssignee.user_id.in_(user_ids))
        rows = await self._db.execute(stmt)
        return [
            DueCard(
                user_id=row[0],
                board_id=row[1],
                board_key=row[2],
                board_name=row[3],
                card_id=row[4],
                number=row[5],
                title=row[6],
                stage_name=row[7],
                due_at=row[8],
            )
            for row in rows.all()
        ]
