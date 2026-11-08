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
from collections.abc import Collection
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_enums import GoalStatus
from app.models.appraisal_goal import AppraisalGoal
from app.models.appraisal_goal_revision import AppraisalGoalRevision
from app.repositories.base import BaseRepository


class AppraisalGoalRepository(BaseRepository[AppraisalGoal]):
    """Goals, always scoped to one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        """Initialize the repository."""
        super().__init__(AppraisalGoal, db, org_id=org_id)
        self._org = org_id

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

    async def for_period(self, profile_id: uuid.UUID, period_start: date) -> list[AppraisalGoal]:
        """Every goal for the person's period, whatever its status, oldest first."""
        result = await self._db.execute(
            self._scoped(select(AppraisalGoal))
            .where(
                AppraisalGoal.profile_id == profile_id,
                AppraisalGoal.target_period_start == period_start,
            )
            .order_by(AppraisalGoal.created_at)
        )
        return list(result.scalars().all())

    async def latest_accepted_before(
        self, profile_id: uuid.UUID, period_start: date
    ) -> list[AppraisalGoal]:
        """The person's accepted goals from their most recent earlier period."""
        latest = (
            select(func.max(AppraisalGoal.target_period_start))
            .where(
                AppraisalGoal.org_id == self._org,
                AppraisalGoal.profile_id == profile_id,
                AppraisalGoal.status == GoalStatus.ACCEPTED,
                AppraisalGoal.target_period_start < period_start,
            )
            .scalar_subquery()
        )
        result = await self._db.execute(
            self._scoped(select(AppraisalGoal))
            .where(
                AppraisalGoal.profile_id == profile_id,
                AppraisalGoal.status == GoalStatus.ACCEPTED,
                AppraisalGoal.target_period_start == latest,
            )
            .order_by(AppraisalGoal.position)
        )
        return list(result.scalars().all())

    async def revisions(self, goal_ids: Collection[uuid.UUID]) -> list[AppraisalGoalRevision]:
        """The history of these goals, oldest first."""
        if not goal_ids:
            return []
        result = await self._db.execute(
            select(AppraisalGoalRevision)
            .where(
                AppraisalGoalRevision.org_id == self._org,
                AppraisalGoalRevision.goal_id.in_(list(goal_ids)),
            )
            .order_by(AppraisalGoalRevision.created_at)
        )
        return list(result.scalars().all())

    async def status_counts(
        self, profile_ids: Collection[uuid.UUID]
    ) -> dict[tuple[uuid.UUID, date, GoalStatus], int]:
        """How many goals each person has per period and status."""
        if not profile_ids:
            return {}
        result = await self._db.execute(
            select(
                AppraisalGoal.profile_id,
                AppraisalGoal.target_period_start,
                AppraisalGoal.status,
                func.count(),
            )
            .where(
                AppraisalGoal.org_id == self._org, AppraisalGoal.profile_id.in_(list(profile_ids))
            )
            .group_by(
                AppraisalGoal.profile_id, AppraisalGoal.target_period_start, AppraisalGoal.status
            )
        )
        return {(r[0], r[1], r[2]): int(r[3]) for r in result.all()}
