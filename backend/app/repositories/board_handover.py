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

"""Card handovers to BUDs, for one org."""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Row, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_enums import BoardHandoverStatus
from app.models.board_handover import BoardCardHandover
from app.models.bud import BUDDocument, BUDStatus


@dataclass(frozen=True)
class HandoverBUD:
    """The few BUD facts a handover shows."""

    number: int
    title: str
    status: BUDStatus


HandoverRow = tuple[BoardCardHandover, HandoverBUD | None]


def _row(row: Row[Any]) -> HandoverRow:
    handover, number, title, status = row
    return handover, None if number is None else HandoverBUD(number, title, status)


class BoardHandoverRepository:
    """Tenant-scoped reads and writes of ``board_card_handovers``."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        self._db = db
        self._org_id = org_id

    async def add(self, row: BoardCardHandover) -> BoardCardHandover:
        """Insert one handover and flush it."""
        self._db.add(row)
        await self._db.flush()
        return row

    async def by_idempotency_key(self, card_id: uuid.UUID, key: uuid.UUID) -> HandoverRow | None:
        """The card's handover made with ``key``, with its BUD."""
        stmt = self._with_bud().where(
            BoardCardHandover.card_id == card_id, BoardCardHandover.idempotency_key == key
        )
        row = (await self._db.execute(stmt)).first()
        return None if row is None else _row(row)

    async def list_for_card(self, card_id: uuid.UUID) -> list[HandoverRow]:
        """The card's handovers, oldest first, each with its BUD."""
        stmt = self._with_bud().where(BoardCardHandover.card_id == card_id)
        stmt = stmt.order_by(BoardCardHandover.handed_over_at, BoardCardHandover.id)
        return [_row(row) for row in (await self._db.execute(stmt)).all()]

    async def count_for_card(self, card_id: uuid.UUID) -> int:
        """How many handovers the card has ever had, returned ones included."""
        stmt = select(func.count()).where(
            BoardCardHandover.org_id == self._org_id, BoardCardHandover.card_id == card_id
        )
        return int((await self._db.execute(stmt)).scalar_one())

    async def active_for_bud(self, bud_id: uuid.UUID) -> BoardCardHandover | None:
        """The BUD's live origin, if a card holds one."""
        stmt = select(BoardCardHandover).where(
            BoardCardHandover.org_id == self._org_id,
            BoardCardHandover.bud_id == bud_id,
            BoardCardHandover.status == BoardHandoverStatus.ACTIVE,
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def on_card_for_bud(self, card_id: uuid.UUID, bud_id: uuid.UUID) -> bool:
        """Whether the card already holds a handover (live or returned) for the BUD."""
        stmt = select(BoardCardHandover.id).where(
            BoardCardHandover.org_id == self._org_id,
            BoardCardHandover.card_id == card_id,
            BoardCardHandover.bud_id == bud_id,
        )
        return (await self._db.execute(stmt)).first() is not None

    def _with_bud(self) -> Select[Any]:
        return (
            select(
                BoardCardHandover, BUDDocument.bud_number, BUDDocument.title, BUDDocument.status
            )
            .outerjoin(
                BUDDocument,
                (BUDDocument.id == BoardCardHandover.bud_id)
                & (BUDDocument.org_id == BoardCardHandover.org_id),
            )
            .where(BoardCardHandover.org_id == self._org_id)
        )
