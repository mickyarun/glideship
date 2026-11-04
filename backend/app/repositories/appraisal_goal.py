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

"""Data access for appraisal goals."""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_enums import GoalStatus
from app.models.appraisal_goal import AppraisalGoal
from app.repositories.base import BaseRepository


class AppraisalGoalRepository(BaseRepository[AppraisalGoal]):
    """Goals, always scoped to one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        """Initialize the repository."""
        super().__init__(AppraisalGoal, db, org_id=org_id)

    async def accepted_for_period(
        self, profile_id: uuid.UUID, period_start: date
    ) -> list[AppraisalGoal]:
        """The person's accepted goals for a review period, in order."""
        result = await self._db.execute(
            self._scoped(select(AppraisalGoal))
            .where(
                AppraisalGoal.profile_id == profile_id,
                AppraisalGoal.target_period_start == period_start,
                AppraisalGoal.status == GoalStatus.ACCEPTED,
            )
            .order_by(AppraisalGoal.position)
        )
        return list(result.scalars().all())
