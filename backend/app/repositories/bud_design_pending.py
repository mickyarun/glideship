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

"""Whether a handed-over BUD still waits for its first design, in one query."""

import uuid

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_enums import BoardHandoverStatus
from app.models.board_handover import BoardCardHandover
from app.models.bud import BUDDesign, BUDStatus


class BUDDesignPendingRepository:
    """Reads for the BUD page's design hint, for one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        self._db = db
        self._org_id = org_id

    async def landed_at_design_without_designs(self, bud_id: uuid.UUID) -> bool:
        """The BUD's live handover landed it at design, and no design row exists for it yet.

        Any design row (pending, generating, ready or failed) means generation started.
        """
        landed = exists().where(
            BoardCardHandover.org_id == self._org_id,
            BoardCardHandover.bud_id == bud_id,
            BoardCardHandover.status == BoardHandoverStatus.ACTIVE,
            BoardCardHandover.target_status == BUDStatus.DESIGN,
        )
        designed = exists().where(BUDDesign.org_id == self._org_id, BUDDesign.bud_id == bud_id)
        stmt = select(landed & ~designed)
        return bool((await self._db.execute(stmt)).scalar_one())
