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


"""Board cycle and lead times in SQL: median and 85th percentile per board, in one statement each.

- Cycle time: from a card's first entry into ``in_progress`` (on any board)
  to its latest entry into ``done`` on the board within the window
  (:func:`latest_done_entries`, the same row throughput counts), so a card
  sent back and done again is one duration, measured to its last finish.
- Idea to prod: from the card's creation to each of its BUDs being
  delivered (the card's ``delivered`` event, one per BUD) within the window.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Subquery, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.board_card import BoardCard
from app.models.board_card_detail import BoardCardEvent
from app.models.board_enums import BoardCardEventType, BoardStageCategory
from app.repositories.board_metrics import latest_done_entries

_MEDIAN = 0.5
_P85 = 0.85


@dataclass(frozen=True)
class DurationRow:
    """How many durations a board had, and their median and 85th percentile in seconds."""

    count: int
    median_seconds: float | None
    p85_seconds: float | None


class BoardDurationRepository:
    """Cycle and lead times for boards in one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        self._db = db
        self._org_id = org_id

    async def cycle_times(
        self, board_ids: list[uuid.UUID], since: datetime
    ) -> dict[uuid.UUID, DurationRow]:
        """Per board: first in-progress entry to the latest done entry, done since ``since``."""
        done = latest_done_entries(self._org_id, board_ids, since)
        start = aliased(BoardCardEvent)
        started = (
            select(func.min(start.created_at))
            .where(
                start.org_id == self._org_id,
                start.card_id == done.c.card_id,
                start.to_category == BoardStageCategory.IN_PROGRESS,
                start.created_at <= done.c.done_at,
            )
            .correlate(done)
            .scalar_subquery()
        )
        secs = func.extract("epoch", done.c.done_at - started)
        return await self._stats(select(done.c.board_id, secs.label("secs")).subquery("cycle"))

    async def lead_times(
        self, board_ids: list[uuid.UUID], since: datetime
    ) -> dict[uuid.UUID, DurationRow]:
        """Per board: card created to each BUD delivered, delivered since ``since``."""
        e = BoardCardEvent
        secs = func.extract("epoch", e.created_at - BoardCard.created_at)
        rows = (
            select(e.board_id, secs.label("secs"))
            .join(BoardCard, BoardCard.id == e.card_id)
            .where(
                e.org_id == self._org_id,
                BoardCard.org_id == self._org_id,
                e.board_id.in_(board_ids),
                e.type == BoardCardEventType.DELIVERED,
                e.created_at >= since,
            )
            .subquery("lead")
        )
        return await self._stats(rows)

    async def _stats(self, rows: Subquery) -> dict[uuid.UUID, DurationRow]:
        secs = rows.c.secs
        stmt = (
            select(
                rows.c.board_id,
                func.count(secs),
                func.percentile_cont(_MEDIAN).within_group(secs),
                func.percentile_cont(_P85).within_group(secs),
            )
            .where(secs.is_not(None))
            .group_by(rows.c.board_id)
        )
        return {
            board_id: DurationRow(
                int(count),
                None if median is None else float(median),
                None if p85 is None else float(p85),
            )
            for board_id, count, median, p85 in (await self._db.execute(stmt)).all()
        }
