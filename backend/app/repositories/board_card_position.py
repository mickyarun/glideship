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

"""Card positions within a stage: neighbours, rebalancing and bulk moves.

Callers hold the stage's row lock (``BoardStageRepository.lock``) while
they read neighbours and write a position, so concurrent moves into one
stage take turns and never compute the same midpoint.
"""

import uuid
from datetime import datetime

from sqlalchemy import ColumnElement, and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_card import BoardCard
from app.models.board_enums import COMPLETED_CATEGORIES, BoardStageCategory
from app.repositories.base import rowcount


def _entry_stamps(category: BoardStageCategory, now: datetime) -> dict[str, object]:
    """The started/completed columns for cards entering ``category``.

    The SQL form of ``services/boards/card_timing.enter_category``.
    """
    stamps: dict[str, object] = {
        "completed_at": (
            func.coalesce(BoardCard.completed_at, now)
            if category in COMPLETED_CATEGORIES
            else None
        )
    }
    if category is BoardStageCategory.IN_PROGRESS:
        stamps["started_at"] = func.coalesce(BoardCard.started_at, now)
    return stamps


class BoardCardPositionRepository:
    """Ordering of cards inside the stages of one org's boards."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        self._db = db
        self._org_id = org_id

    def _in_stage(
        self, stage_id: uuid.UUID, exclude: uuid.UUID | None
    ) -> list[ColumnElement[bool]]:
        clauses = [
            BoardCard.org_id == self._org_id,
            BoardCard.stage_id == stage_id,
            BoardCard.archived_at.is_(None),
        ]
        if exclude is not None:
            clauses.append(BoardCard.id != exclude)
        return clauses

    async def has_cards(self, stage_id: uuid.UUID) -> bool:
        """Whether any card, open or archived, sits in the stage."""
        stmt = select(BoardCard.id).where(
            BoardCard.org_id == self._org_id, BoardCard.stage_id == stage_id
        )
        return (await self._db.execute(stmt.limit(1))).first() is not None

    async def position_of(self, stage_id: uuid.UUID, card_id: uuid.UUID) -> float | None:
        """An open card's position, or None when it isn't open in this stage."""
        stmt = select(BoardCard.position).where(
            *self._in_stage(stage_id, None), BoardCard.id == card_id
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def last_position(
        self, stage_id: uuid.UUID, exclude: uuid.UUID | None = None
    ) -> float | None:
        """The bottom open card's position, or None for an empty stage."""
        stmt = select(func.max(BoardCard.position)).where(*self._in_stage(stage_id, exclude))
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def next_after(
        self, stage_id: uuid.UUID, card_id: uuid.UUID, position: float, exclude: uuid.UUID | None
    ) -> float | None:
        """The position just below ``card_id`` in (position, id) order."""
        later = or_(
            BoardCard.position > position,
            and_(BoardCard.position == position, BoardCard.id > card_id),
        )
        stmt = select(func.min(BoardCard.position)).where(
            *self._in_stage(stage_id, exclude), later
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def previous_before(
        self, stage_id: uuid.UUID, card_id: uuid.UUID, position: float, exclude: uuid.UUID | None
    ) -> float | None:
        """The position just above ``card_id`` in (position, id) order."""
        earlier = or_(
            BoardCard.position < position,
            and_(BoardCard.position == position, BoardCard.id < card_id),
        )
        stmt = select(func.max(BoardCard.position)).where(
            *self._in_stage(stage_id, exclude), earlier
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def rebalance(self, stage_id: uuid.UUID, gap: float) -> int:
        """Respace the stage's open cards ``gap`` apart, keeping their order."""
        ranked = (
            select(
                BoardCard.id,
                func.row_number().over(order_by=(BoardCard.position, BoardCard.id)).label("rank"),
            )
            .where(*self._in_stage(stage_id, None))
            .subquery()
        )
        stmt = (
            update(BoardCard)
            .where(BoardCard.id == ranked.c.id)
            .values(position=ranked.c.rank * gap)
            .execution_options(synchronize_session=False)
        )
        return rowcount(await self._db.execute(stmt))

    async def move_all(
        self,
        from_stage: uuid.UUID,
        to_stage: uuid.UUID,
        to_category: BoardStageCategory,
        *,
        start: float,
        gap: float,
        now: datetime,
    ) -> int:
        """Move every card of ``from_stage`` to the bottom of ``to_stage``, in order.

        Open cards keep their order; archived cards follow them. The
        started and completed stamps follow the target stage's category,
        the same rule a single move applies.
        """
        ranked = (
            select(
                BoardCard.id,
                func.row_number()
                .over(
                    order_by=(BoardCard.archived_at.is_not(None), BoardCard.position, BoardCard.id)
                )
                .label("rank"),
            )
            .where(BoardCard.org_id == self._org_id, BoardCard.stage_id == from_stage)
            .subquery()
        )
        values: dict[str, object] = {
            "stage_id": to_stage,
            "position": start + ranked.c.rank * gap,
            **_entry_stamps(to_category, now),
        }
        stmt = (
            update(BoardCard)
            .where(BoardCard.id == ranked.c.id)
            .values(values)
            .execution_options(synchronize_session=False)
        )
        return rowcount(await self._db.execute(stmt))

    async def restamp(
        self, stage_id: uuid.UUID, category: BoardStageCategory, *, now: datetime
    ) -> int:
        """Re-stamp every card in a stage whose category just changed."""
        stmt = (
            update(BoardCard)
            .where(BoardCard.org_id == self._org_id, BoardCard.stage_id == stage_id)
            .values(_entry_stamps(category, now))
            .execution_options(synchronize_session=False)
        )
        return rowcount(await self._db.execute(stmt))
