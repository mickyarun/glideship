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

"""Whether a BUD still waits for its first design, in one query."""

import uuid

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bud import BUDDesign


class BUDDesignPendingRepository:
    """Reads for the BUD page's design hint, for one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        self._db = db
        self._org_id = org_id

    async def has_no_designs(self, bud_id: uuid.UUID) -> bool:
        """No design row exists for the BUD yet.

        Any design row (pending, generating, ready or failed) means generation started.
        """
        designed = exists().where(BUDDesign.org_id == self._org_id, BUDDesign.bud_id == bud_id)
        return not bool((await self._db.execute(select(designed))).scalar_one())
