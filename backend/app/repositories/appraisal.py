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

"""Data access for appraisals and the people who can be enrolled."""

import uuid
from collections.abc import Collection
from datetime import date, datetime
from typing import Literal

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal import Appraisal
from app.models.appraisal_enums import AppraisalStatus, DraftingMode, DraftStatus
from app.models.employee_profile import EmployeeProfile, EmployeeStatus
from app.models.employee_reporting_manager import EmployeeReportingManager
from app.models.user import User
from app.repositories.base import BaseRepository, rowcount

# Which reminder stream's announcement an update records.
NotifiedColumn = Literal["self_notified_at", "review_notified_at", "result_notified_at"]

# Appraisals still in progress: a manager change or an exit affects them.
OPEN = (
    AppraisalStatus.ENROLLED,
    AppraisalStatus.SELF_REVIEW,
    AppraisalStatus.MANAGER_REVIEW,
    AppraisalStatus.CALIBRATION,
)


class AppraisalRepository(BaseRepository[Appraisal]):
    """Appraisals, always scoped to one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        """Initialize the repository."""
        super().__init__(Appraisal, db, org_id=org_id)
        self._org = org_id

    async def for_cycle(self, cycle_id: uuid.UUID) -> list[Appraisal]:
        """Every appraisal in a cycle."""
        result = await self._db.execute(
            self._scoped(select(Appraisal)).where(Appraisal.cycle_id == cycle_id)
        )
        return list(result.scalars().all())

    async def for_profile_in_cycle(
        self, profile_id: uuid.UUID, cycle_id: uuid.UUID
    ) -> Appraisal | None:
        """The person's appraisal in a cycle, if enrolled."""
        result = await self._db.execute(
            self._scoped(select(Appraisal)).where(
                Appraisal.profile_id == profile_id, Appraisal.cycle_id == cycle_id
            )
        )
        return result.scalar_one_or_none()

    async def open_for_profile(self, profile_id: uuid.UUID) -> list[Appraisal]:
        """The person's appraisals still in progress."""
        result = await self._db.execute(
            self._scoped(select(Appraisal)).where(
                Appraisal.profile_id == profile_id, Appraisal.status.in_(OPEN)
            )
        )
        return list(result.scalars().all())

    async def move_scorer(
        self, profile_id: uuid.UUID, manager_user_id: uuid.UUID
    ) -> list[uuid.UUID]:
        """Point the person's open appraisals at a new primary manager; the ids moved."""
        result = await self._db.execute(
            update(Appraisal)
            .where(
                Appraisal.org_id == self._org,
                Appraisal.profile_id == profile_id,
                Appraisal.status.in_(OPEN),
                Appraisal.manager_user_id != manager_user_id,
            )
            .values(manager_user_id=manager_user_id)
            .returning(Appraisal.id)
        )
        return list(result.scalars().all())

    async def enrollable_profiles(
        self, cutoff: date, exclude: Collection[uuid.UUID] = ()
    ) -> list[EmployeeProfile]:
        """Active people (not on notice) with a working account who joined by ``cutoff``."""
        stmt = (
            select(EmployeeProfile)
            .join(User, User.id == EmployeeProfile.user_id)
            .where(
                EmployeeProfile.org_id == self._org,
                EmployeeProfile.status == EmployeeStatus.ACTIVE,
                User.is_active.is_(True),
                or_(
                    EmployeeProfile.date_of_joining.is_(None),
                    EmployeeProfile.date_of_joining <= cutoff,
                ),
            )
        )
        if exclude:
            stmt = stmt.where(EmployeeProfile.id.not_in(exclude))
        return list((await self._db.execute(stmt)).scalars().all())

    async def profiles_by_id(
        self, profile_ids: Collection[uuid.UUID]
    ) -> dict[uuid.UUID, EmployeeProfile]:
        """Profiles by id, for the people in a cycle."""
        if not profile_ids:
            return {}
        result = await self._db.execute(
            select(EmployeeProfile).where(
                EmployeeProfile.org_id == self._org, EmployeeProfile.id.in_(profile_ids)
            )
        )
        return {p.id: p for p in result.scalars().all()}

    async def report_profile_ids(self, manager_user_id: uuid.UUID) -> list[uuid.UUID]:
        """Profiles that report to this person, directly."""
        result = await self._db.execute(
            select(EmployeeReportingManager.profile_id).where(
                EmployeeReportingManager.org_id == self._org,
                EmployeeReportingManager.manager_user_id == manager_user_id,
            )
        )
        return list(result.scalars().all())

    async def queue_summaries(self, cycle_id: uuid.UUID) -> int:
        """Mark each AI-mode appraisal in a cycle for a period summary."""
        result = await self._db.execute(
            update(Appraisal)
            .where(
                Appraisal.org_id == self._org,
                Appraisal.cycle_id == cycle_id,
                Appraisal.drafting_mode == DraftingMode.AI,
                Appraisal.status != AppraisalStatus.WITHDRAWN,
                Appraisal.period_summary_status == DraftStatus.NONE,
            )
            .values(period_summary_status=DraftStatus.PENDING, summary_attempts=0)
        )
        return rowcount(result)

    async def for_profiles(self, profile_ids: Collection[uuid.UUID]) -> list[Appraisal]:
        """These people's appraisals in every cycle that has opened."""
        if not profile_ids:
            return []
        result = await self._db.execute(
            self._scoped(select(Appraisal)).where(Appraisal.profile_id.in_(list(profile_ids)))
        )
        return list(result.scalars().all())

    async def live_in_cycles(self, cycle_ids: Collection[uuid.UUID]) -> list[Appraisal]:
        """Every appraisal in these cycles that hasn't been withdrawn."""
        if not cycle_ids:
            return []
        result = await self._db.execute(
            self._scoped(select(Appraisal)).where(
                Appraisal.cycle_id.in_(list(cycle_ids)),
                Appraisal.status != AppraisalStatus.WITHDRAWN,
            )
        )
        return list(result.scalars().all())

    async def mark_notified(
        self, ids: Collection[uuid.UUID], column: NotifiedColumn, at: datetime
    ) -> None:
        """Record that one step of these appraisals was announced."""
        if ids:
            await self._db.execute(
                update(Appraisal)
                .where(Appraisal.org_id == self._org, Appraisal.id.in_(list(ids)))
                .values({column: at})
            )
