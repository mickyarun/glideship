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

"""Data access for manager feedback items."""

import uuid

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_enums import FeedbackStatus
from app.models.appraisal_manager_feedback import AppraisalManagerFeedback
from app.repositories.base import BaseRepository, rowcount


class AppraisalFeedbackRepository(BaseRepository[AppraisalManagerFeedback]):
    """Feedback items, always scoped to one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        """Initialize the repository."""
        super().__init__(AppraisalManagerFeedback, db, org_id=org_id)
        self._org = org_id

    async def move_open(self, profile_id: uuid.UUID, manager_user_id: uuid.UUID) -> int:
        """Hand the person's open feedback items to a new manager."""
        result = await self._db.execute(
            update(AppraisalManagerFeedback)
            .where(
                AppraisalManagerFeedback.org_id == self._org,
                AppraisalManagerFeedback.profile_id == profile_id,
                AppraisalManagerFeedback.status == FeedbackStatus.OPEN,
                AppraisalManagerFeedback.manager_user_id != manager_user_id,
            )
            .values(manager_user_id=manager_user_id)
        )
        return rowcount(result)
