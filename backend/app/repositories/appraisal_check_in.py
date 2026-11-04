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

"""Data access for check-ins and the links and goal values on them."""

import uuid
from collections.abc import Collection
from datetime import date

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_enums import DraftStatus
from app.models.appraisal_evidence_link import AppraisalEvidenceLink
from app.models.appraisal_goal_value import AppraisalGoalValue
from app.repositories.base import BaseRepository

MAX_LINKS = 5


class AppraisalCheckInRepository(BaseRepository[AppraisalCheckIn]):
    """Check-ins, always scoped to one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        """Initialize the repository."""
        super().__init__(AppraisalCheckIn, db, org_id=org_id)
        self._org = org_id

    async def for_cycle(self, cycle_id: uuid.UUID) -> list[AppraisalCheckIn]:
        """Every check-in in a cycle."""
        result = await self._db.execute(
            self._scoped(select(AppraisalCheckIn)).where(AppraisalCheckIn.cycle_id == cycle_id)
        )
        return list(result.scalars().all())

    async def for_person_in_cycle(
        self, profile_id: uuid.UUID, cycle_id: uuid.UUID
    ) -> list[AppraisalCheckIn]:
        """One person's check-ins in a cycle, oldest first."""
        result = await self._db.execute(
            self._scoped(select(AppraisalCheckIn))
            .where(
                AppraisalCheckIn.profile_id == profile_id, AppraisalCheckIn.cycle_id == cycle_id
            )
            .order_by(AppraisalCheckIn.period_start)
        )
        return list(result.scalars().all())

    async def for_profiles(
        self, profile_ids: Collection[uuid.UUID], *, since: date | None = None
    ) -> list[AppraisalCheckIn]:
        """These people's check-ins, newest first."""
        if not profile_ids:
            return []
        stmt = self._scoped(select(AppraisalCheckIn)).where(
            AppraisalCheckIn.profile_id.in_(profile_ids)
        )
        if since is not None:
            stmt = stmt.where(AppraisalCheckIn.period_start >= since)
        result = await self._db.execute(stmt.order_by(AppraisalCheckIn.period_start.desc()))
        return list(result.scalars().all())

    async def latest_for_profiles(
        self, profile_ids: Collection[uuid.UUID]
    ) -> list[AppraisalCheckIn]:
        """Each person's most recent check-in, one row per person."""
        if not profile_ids:
            return []
        result = await self._db.execute(
            self._scoped(select(AppraisalCheckIn))
            .where(AppraisalCheckIn.profile_id.in_(profile_ids))
            .order_by(AppraisalCheckIn.profile_id, AppraisalCheckIn.period_start.desc())
            .distinct(AppraisalCheckIn.profile_id)
        )
        return list(result.scalars().all())

    async def cancel_pending_drafts(self, profile_id: uuid.UUID) -> None:
        """Stop any AI draft still waiting for this person."""
        await self._db.execute(
            update(AppraisalCheckIn)
            .where(
                AppraisalCheckIn.org_id == self._org,
                AppraisalCheckIn.profile_id == profile_id,
                AppraisalCheckIn.draft_status == DraftStatus.PENDING,
            )
            .values(draft_status=DraftStatus.NONE, draft_claimed_at=None)
        )

    async def links(self, check_in_id: uuid.UUID) -> list[AppraisalEvidenceLink]:
        """The links on one check-in, oldest first."""
        result = await self._db.execute(
            select(AppraisalEvidenceLink)
            .where(
                AppraisalEvidenceLink.org_id == self._org,
                AppraisalEvidenceLink.check_in_id == check_in_id,
            )
            .order_by(AppraisalEvidenceLink.created_at)
        )
        return list(result.scalars().all())

    async def goal_values(self, check_in_id: uuid.UUID) -> list[AppraisalGoalValue]:
        """The goal values on one check-in."""
        result = await self._db.execute(
            select(AppraisalGoalValue).where(
                AppraisalGoalValue.org_id == self._org,
                AppraisalGoalValue.check_in_id == check_in_id,
            )
        )
        return list(result.scalars().all())

    async def goal_value(
        self, check_in_id: uuid.UUID, goal_id: uuid.UUID
    ) -> AppraisalGoalValue | None:
        """One goal's value on one check-in."""
        result = await self._db.execute(
            select(AppraisalGoalValue).where(
                AppraisalGoalValue.org_id == self._org,
                AppraisalGoalValue.check_in_id == check_in_id,
                AppraisalGoalValue.goal_id == goal_id,
            )
        )
        return result.scalar_one_or_none()

    async def link(self, link_id: uuid.UUID) -> AppraisalEvidenceLink | None:
        """One link by id."""
        result = await self._db.execute(
            select(AppraisalEvidenceLink).where(
                AppraisalEvidenceLink.org_id == self._org, AppraisalEvidenceLink.id == link_id
            )
        )
        return result.scalar_one_or_none()
