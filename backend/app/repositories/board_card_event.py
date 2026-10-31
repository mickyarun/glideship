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

"""Data access for card history, scoped to an organization."""

import uuid
from datetime import datetime

from sqlalchemy import and_, cast, func, insert, literal, or_, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.board_card import BoardCard
from app.models.board_card_detail import BoardCardEvent
from app.models.board_enums import BoardCardEventType, BoardStageCategory
from app.repositories.base import BaseRepository


class BoardCardEventRepository(BaseRepository[BoardCardEvent]):
    """Tenant-scoped repository for card events."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        super().__init__(BoardCardEvent, db, org_id=org_id)

    async def latest_edit(
        self, card_id: uuid.UUID, actor_id: uuid.UUID, since: datetime
    ) -> BoardCardEvent | None:
        """The actor's newest ``edited`` event on the card since ``since``, locked."""
        stmt = self._scoped(
            select(BoardCardEvent)
            .where(
                BoardCardEvent.card_id == card_id,
                BoardCardEvent.actor_id == actor_id,
                BoardCardEvent.type == BoardCardEventType.EDITED,
                BoardCardEvent.created_at >= since,
            )
            .order_by(BoardCardEvent.created_at.desc(), BoardCardEvent.id.desc())
            .limit(1)
            .with_for_update()
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def has_for_bud(
        self, card_id: uuid.UUID, event_type: BoardCardEventType, bud_id: uuid.UUID
    ) -> bool:
        """Whether the card already has a ``event_type`` event naming the BUD."""
        stmt = self._scoped(
            select(BoardCardEvent.id).where(
                BoardCardEvent.card_id == card_id,
                BoardCardEvent.type == event_type,
                BoardCardEvent.detail["bud_id"].astext == str(bud_id),
            )
        )
        return (await self._db.execute(stmt.limit(1))).first() is not None

    async def page(
        self, card_id: uuid.UUID, *, before: uuid.UUID | None, limit: int
    ) -> list[BoardCardEvent]:
        """Up to ``limit`` of the card's events, newest first, older than ``before``."""
        stmt = self._scoped(select(BoardCardEvent).where(BoardCardEvent.card_id == card_id))
        if before is not None:
            anchor = aliased(BoardCardEvent)
            at = (
                select(anchor.created_at)
                .where(anchor.id == before, anchor.card_id == card_id)
                .scalar_subquery()
            )
            stmt = stmt.where(
                or_(
                    BoardCardEvent.created_at < at,
                    and_(BoardCardEvent.created_at == at, BoardCardEvent.id < before),
                )
            )
        stmt = stmt.order_by(BoardCardEvent.created_at.desc(), BoardCardEvent.id.desc())
        return list((await self._db.execute(stmt.limit(limit))).scalars().all())

    async def record_stage_moves(
        self,
        from_stage: uuid.UUID,
        to_stage: uuid.UUID,
        *,
        board_id: uuid.UUID,
        actor_id: uuid.UUID,
        from_category: BoardStageCategory,
        to_category: BoardStageCategory,
    ) -> None:
        """One ``moved`` event for every card still in ``from_stage``, in one statement."""
        table = BoardCardEvent.__table__.c
        cards = select(
            func.gen_random_uuid(),
            literal(self._org_id, UUID(as_uuid=True)),
            BoardCard.id,
            literal(board_id, UUID(as_uuid=True)),
            cast(literal(BoardCardEventType.MOVED.value), table.type.type),
            literal(actor_id, UUID(as_uuid=True)),
            literal(from_stage, UUID(as_uuid=True)),
            literal(to_stage, UUID(as_uuid=True)),
            cast(literal(from_category.value), table.from_category.type),
            cast(literal(to_category.value), table.to_category.type),
        ).where(BoardCard.org_id == self._org_id, BoardCard.stage_id == from_stage)
        columns = [
            "id",
            "org_id",
            "card_id",
            "board_id",
            "type",
            "actor_id",
            "from_stage_id",
            "to_stage_id",
            "from_category",
            "to_category",
        ]
        await self._db.execute(insert(BoardCardEvent).from_select(columns, cards))
