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

"""Data access for card checklist items, scoped to an organization."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_card_detail import BoardCardChecklistItem
from app.repositories.base import BaseRepository


class BoardCardChecklistRepository(BaseRepository[BoardCardChecklistItem]):
    """Tenant-scoped repository for checklist items."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        super().__init__(BoardCardChecklistItem, db, org_id=org_id)

    async def list_for_card(self, card_id: uuid.UUID) -> list[BoardCardChecklistItem]:
        """The card's checklist, top to bottom."""
        stmt = self._scoped(
            select(BoardCardChecklistItem)
            .where(BoardCardChecklistItem.card_id == card_id)
            .order_by(BoardCardChecklistItem.position, BoardCardChecklistItem.id)
        )
        return list((await self._db.execute(stmt)).scalars().all())

    async def get_in_card(
        self, card_id: uuid.UUID, item_id: uuid.UUID
    ) -> BoardCardChecklistItem | None:
        """One item, or None when it belongs to another card."""
        stmt = self._scoped(
            select(BoardCardChecklistItem).where(
                BoardCardChecklistItem.id == item_id, BoardCardChecklistItem.card_id == card_id
            )
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def last_position(self, card_id: uuid.UUID) -> float | None:
        """The bottom item's position, or None for an empty checklist."""
        stmt = self._scoped(
            select(func.max(BoardCardChecklistItem.position)).where(
                BoardCardChecklistItem.card_id == card_id
            )
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()
