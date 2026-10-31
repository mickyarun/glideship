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


"""Every handover confirm's idempotency key, per card, for one org."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_handover import BoardCardHandoverKey


class BoardHandoverKeyRepository:
    """Tenant-scoped reads and writes of ``board_card_handover_keys``."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        self._db = db
        self._org_id = org_id

    async def handover_for(self, card_id: uuid.UUID, key: uuid.UUID) -> uuid.UUID | None:
        """The handover a confirm with ``key`` on the card made or reused."""
        stmt = select(BoardCardHandoverKey.handover_id).where(
            BoardCardHandoverKey.org_id == self._org_id,
            BoardCardHandoverKey.card_id == card_id,
            BoardCardHandoverKey.idempotency_key == key,
        )
        found: uuid.UUID | None = (await self._db.execute(stmt)).scalar_one_or_none()
        return found

    async def add(self, card_id: uuid.UUID, key: uuid.UUID, handover_id: uuid.UUID) -> None:
        """Keep ``key`` as one of the card's confirms, pointing at its handover."""
        self._db.add(
            BoardCardHandoverKey(
                org_id=self._org_id, card_id=card_id, idempotency_key=key, handover_id=handover_id
            )
        )
        await self._db.flush()
