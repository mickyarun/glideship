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

"""Goal values: what the person reported for each goal on each check-in."""

import uuid
from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_goal_value import AppraisalGoalValue


class AppraisalGoalValueRepository:
    """Goal values, always scoped to one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        """Initialize the repository."""
        self._db = db
        self._org = org_id

    async def for_check_ins(self, check_in_ids: Collection[uuid.UUID]) -> list[AppraisalGoalValue]:
        """Every value on these check-ins, in one query."""
        if not check_in_ids:
            return []
        result = await self._db.execute(
            select(AppraisalGoalValue).where(
                AppraisalGoalValue.org_id == self._org,
                AppraisalGoalValue.check_in_id.in_(list(check_in_ids)),
            )
        )
        return list(result.scalars().all())
