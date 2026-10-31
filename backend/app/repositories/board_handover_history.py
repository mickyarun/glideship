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

"""A card's send-backs and re-handovers, read from its own card events."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_card_detail import BoardCardEvent
from app.models.board_enums import BoardCardEventType
from app.models.user import User


@dataclass(frozen=True)
class HandoverHistoryRow:
    """One ``returned`` event, or a ``handed_over`` event that reused a sent-back BUD."""

    bud_id: str
    at: datetime
    type: BoardCardEventType
    reason: str | None
    by_name: str | None


class BoardHandoverHistoryRepository:
    """Handover history for one org's cards."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        self._db = db
        self._org_id = org_id

    async def for_card(self, card_id: uuid.UUID, *, per_bud: int) -> list[HandoverHistoryRow]:
        """The card's history in one statement: newest first, at most ``per_bud`` per BUD."""
        event = BoardCardEvent
        bud = event.detail["bud_id"].astext
        again = and_(
            event.type == BoardCardEventType.HANDED_OVER, event.detail.contains({"again": True})
        )
        ranked = (
            select(
                bud.label("bud_id"),
                event.created_at.label("at"),
                event.type.label("type"),
                event.detail["reason"].astext.label("reason"),
                func.coalesce(User.name, event.actor_label).label("by_name"),
                func.row_number()
                .over(partition_by=bud, order_by=(event.created_at.desc(), event.id.desc()))
                .label("rank"),
            )
            .outerjoin(User, User.id == event.actor_id)
            .where(
                event.org_id == self._org_id,
                event.card_id == card_id,
                bud.is_not(None),
                or_(event.type == BoardCardEventType.RETURNED, again),
            )
            .subquery()
        )
        stmt = (
            select(ranked.c.bud_id, ranked.c.at, ranked.c.type, ranked.c.reason, ranked.c.by_name)
            .where(ranked.c.rank <= per_bud)
            .order_by(ranked.c.at.desc(), ranked.c.rank)
        )
        rows = (await self._db.execute(stmt)).all()
        return [HandoverHistoryRow(*row) for row in rows]
