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
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, Row, Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_card import BoardCard
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


def live_handover() -> ColumnElement[bool]:
    """A handover that still counts on its card: active, and its BUD neither gone nor discarded.

    For a query joining ``BoardCardHandover`` to ``BUDDocument`` on the BUD.
    A BUD discarded on the dev side keeps its row active (a restore brings
    it back), but no longer counts toward the card's delivery or moves.
    """
    return (
        (BoardCardHandover.status == BoardHandoverStatus.ACTIVE)
        & BoardCardHandover.bud_id.is_not(None)
        & (BUDDocument.status != BUDStatus.DISCARDED)
    )


def _on_bud() -> ColumnElement[bool]:
    return (BUDDocument.id == BoardCardHandover.bud_id) & (
        BUDDocument.org_id == BoardCardHandover.org_id
    )


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

    async def on_card(self, card_id: uuid.UUID, handover_id: uuid.UUID) -> HandoverRow | None:
        """One of the card's handovers, with its BUD."""
        stmt = self._with_bud().where(
            BoardCardHandover.card_id == card_id, BoardCardHandover.id == handover_id
        )
        row = (await self._db.execute(stmt)).first()
        return None if row is None else _row(row)

    async def list_for_card(self, card_id: uuid.UUID) -> list[HandoverRow]:
        """The card's handovers, oldest first, each with its BUD."""
        stmt = self._with_bud().where(BoardCardHandover.card_id == card_id)
        stmt = stmt.order_by(BoardCardHandover.handed_over_at, BoardCardHandover.id)
        return [_row(row) for row in (await self._db.execute(stmt)).all()]

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

    async def cards_for_bud(self, bud_id: uuid.UUID) -> list[tuple[uuid.UUID, uuid.UUID]]:
        """``(board_id, card_id)`` of each card holding a handover of the BUD, live or returned."""
        stmt = (
            select(BoardCard.board_id, BoardCard.id)
            .join(
                BoardCardHandover,
                (BoardCardHandover.card_id == BoardCard.id)
                & (BoardCardHandover.org_id == BoardCard.org_id),
            )
            .where(BoardCardHandover.org_id == self._org_id, BoardCardHandover.bud_id == bud_id)
            .order_by(BoardCard.id)
        )
        return [(row[0], row[1]) for row in (await self._db.execute(stmt)).all()]

    async def latest_for_bud(self, bud_id: uuid.UUID) -> BoardCardHandover | None:
        """The BUD's live origin, else the handover most recently made for it."""
        stmt = (
            select(BoardCardHandover)
            .where(BoardCardHandover.org_id == self._org_id, BoardCardHandover.bud_id == bud_id)
            .order_by(
                (BoardCardHandover.status == BoardHandoverStatus.ACTIVE).desc(),
                BoardCardHandover.handed_over_at.desc(),
                BoardCardHandover.id.desc(),
            )
            .limit(1)
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def returned_discarded(self, card_id: uuid.UUID) -> BoardCardHandover | None:
        """The card's most recently returned handover whose BUD is still discarded."""
        stmt = (
            select(BoardCardHandover)
            .join(BUDDocument, _on_bud())
            .where(
                BoardCardHandover.org_id == self._org_id,
                BoardCardHandover.card_id == card_id,
                BoardCardHandover.status == BoardHandoverStatus.RETURNED,
                BUDDocument.status == BUDStatus.DISCARDED,
            )
            .order_by(BoardCardHandover.returned_at.desc(), BoardCardHandover.id.desc())
            .limit(1)
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def active_bud_statuses(
        self, card_id: uuid.UUID, *, excluding: uuid.UUID | None = None
    ) -> list[BUDStatus]:
        """The status of each BUD the card holds a live handover of (see :func:`live_handover`)."""
        stmt = (
            select(BUDDocument.status)
            .join(BoardCardHandover, _on_bud())
            .where(
                BoardCardHandover.org_id == self._org_id,
                BoardCardHandover.card_id == card_id,
                live_handover(),
            )
        )
        if excluding is not None:
            stmt = stmt.where(BUDDocument.id != excluding)
        return list((await self._db.execute(stmt)).scalars().all())

    async def count_live_for_card(self, card_id: uuid.UUID) -> int:
        """How many live handovers the card holds (see :func:`live_handover`)."""
        stmt = (
            select(func.count())
            .select_from(BoardCardHandover)
            .join(BUDDocument, _on_bud())
            .where(
                BoardCardHandover.org_id == self._org_id,
                BoardCardHandover.card_id == card_id,
                live_handover(),
            )
        )
        return int((await self._db.execute(stmt)).scalar_one())

    async def set_stage_start_failed(self, handover_id: uuid.UUID, at: datetime | None) -> None:
        """Mark (or clear, with None) a failed start of the handover's target stage."""
        await self._db.execute(
            update(BoardCardHandover)
            .where(BoardCardHandover.org_id == self._org_id, BoardCardHandover.id == handover_id)
            .values(stage_start_failed_at=at)
        )

    def _with_bud(self) -> Select[Any]:
        return (
            select(
                BoardCardHandover, BUDDocument.bud_number, BUDDocument.title, BUDDocument.status
            )
            .outerjoin(BUDDocument, _on_bud())
            .where(BoardCardHandover.org_id == self._org_id)
        )
