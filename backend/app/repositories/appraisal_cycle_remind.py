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

"""Claiming the day for HR's manual reminder, so two clicks can't both send."""

import uuid
from datetime import datetime

from sqlalchemy import or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_cycle import AppraisalCycle
from app.repositories.appraisal_cycle import RUNNING


class AppraisalCycleRemindRepository:
    """The reminder stamp on one org's cycles."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        """Initialize the repository."""
        self._db = db
        self._org = org_id

    async def claim_day(self, cycle_id: uuid.UUID, day_start: datetime, now: datetime) -> bool:
        """Stamp the cycle as reminded now, unless it was already reminded since
        ``day_start`` or isn't running; whether this call won.

        One conditional UPDATE: of two requests at once, only one gets the row.
        """
        cycle = AppraisalCycle
        result = await self._db.execute(
            update(cycle)
            .where(
                cycle.id == cycle_id,
                cycle.org_id == self._org,
                cycle.status.in_(RUNNING),
                or_(cycle.hr_reminded_at.is_(None), cycle.hr_reminded_at < day_start),
            )
            .values(hr_reminded_at=now)
            .returning(cycle.id)
            .execution_options(synchronize_session=False)
        )
        return result.scalar_one_or_none() is not None
