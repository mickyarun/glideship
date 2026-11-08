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
from collections.abc import Collection
from datetime import date, datetime

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal import Appraisal
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import AppraisalStatus, CycleStatus, FeedbackStatus
from app.models.appraisal_manager_feedback import AppraisalManagerFeedback
from app.repositories.appraisal import OPEN
from app.repositories.base import BaseRepository, rowcount


class AppraisalFeedbackRepository(BaseRepository[AppraisalManagerFeedback]):
    """Feedback items, always scoped to one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        """Initialize the repository."""
        super().__init__(AppraisalManagerFeedback, db, org_id=org_id)
        self._org = org_id

    async def for_cycles(self, cycle_ids: Collection[uuid.UUID]) -> list[AppraisalManagerFeedback]:
        """Every feedback item in these cycles, oldest period first."""
        if not cycle_ids:
            return []
        result = await self._db.execute(
            self._scoped(select(AppraisalManagerFeedback))
            .where(AppraisalManagerFeedback.cycle_id.in_(list(cycle_ids)))
            .order_by(AppraisalManagerFeedback.period_start)
        )
        return list(result.scalars().all())

    async def for_manager(self, manager_user_id: uuid.UUID) -> list[AppraisalManagerFeedback]:
        """The items a manager holds, newest period first."""
        result = await self._db.execute(
            self._scoped(select(AppraisalManagerFeedback))
            .where(AppraisalManagerFeedback.manager_user_id == manager_user_id)
            .order_by(AppraisalManagerFeedback.period_start.desc())
            .limit(200)
        )
        return list(result.scalars().all())

    async def for_profiles(
        self, profile_ids: Collection[uuid.UUID]
    ) -> list[AppraisalManagerFeedback]:
        """The items about these people, newest period first."""
        if not profile_ids:
            return []
        result = await self._db.execute(
            self._scoped(select(AppraisalManagerFeedback))
            .where(AppraisalManagerFeedback.profile_id.in_(list(profile_ids)))
            .order_by(AppraisalManagerFeedback.period_start.desc())
        )
        return list(result.scalars().all())

    async def covering(
        self, cycle_id: uuid.UUID, profile_id: uuid.UUID, period_end: date
    ) -> AppraisalManagerFeedback | None:
        """The cycle's item whose period ends with a check-in's: the feedback shown on it."""
        result = await self._db.execute(
            self._scoped(select(AppraisalManagerFeedback)).where(
                AppraisalManagerFeedback.cycle_id == cycle_id,
                AppraisalManagerFeedback.profile_id == profile_id,
                AppraisalManagerFeedback.period_end == period_end,
            )
        )
        return result.scalars().first()

    async def profile_ids_for_period(
        self, cycle_id: uuid.UUID, period_start: date
    ) -> set[uuid.UUID]:
        """Who already has an item for this period in this cycle."""
        result = await self._db.execute(
            select(AppraisalManagerFeedback.profile_id).where(
                AppraisalManagerFeedback.org_id == self._org,
                AppraisalManagerFeedback.cycle_id == cycle_id,
                AppraisalManagerFeedback.period_start == period_start,
            )
        )
        return set(result.scalars().all())

    async def with_open_items(
        self, cycle_ids: Collection[uuid.UUID]
    ) -> list[AppraisalManagerFeedback]:
        """Items in each (manager, cycle, period) group that still has one open.

        People who were withdrawn are left out altogether: their items can't
        be written any more, so nobody is reminded about them.
        """
        if not cycle_ids:
            return []
        item = AppraisalManagerFeedback
        live = and_(
            Appraisal.cycle_id == item.cycle_id,
            Appraisal.profile_id == item.profile_id,
            Appraisal.status != AppraisalStatus.WITHDRAWN,
        )
        in_cycles = and_(item.org_id == self._org, item.cycle_id.in_(list(cycle_ids)))
        open_group = (
            select(item.manager_user_id, item.cycle_id, item.period_start)
            .join(Appraisal, live)
            .where(in_cycles, item.status == FeedbackStatus.OPEN)
            .distinct()
            .subquery()
        )
        result = await self._db.execute(
            select(item)
            .join(Appraisal, live)
            .join(
                open_group,
                and_(
                    item.manager_user_id == open_group.c.manager_user_id,
                    item.cycle_id == open_group.c.cycle_id,
                    item.period_start == open_group.c.period_start,
                ),
            )
            .where(in_cycles)
        )
        return list(result.scalars().all())

    async def mark_notified(self, ids: Collection[uuid.UUID], at: datetime) -> None:
        """Record that these items' opening was announced."""
        if ids:
            await self._db.execute(
                update(AppraisalManagerFeedback)
                .where(
                    AppraisalManagerFeedback.org_id == self._org,
                    AppraisalManagerFeedback.id.in_(list(ids)),
                )
                .values(notified_at=at)
            )

    async def move_open(self, profile_id: uuid.UUID, manager_user_id: uuid.UUID) -> int:
        """Hand the person's open items to a new manager, where they now score.

        Only items whose appraisal moved with them: still in progress, in a
        cycle that hasn't closed, and scored by ``manager_user_id``. An item
        on a shared appraisal stays put, since the writer must be its scorer.
        """
        item = AppraisalManagerFeedback
        scored_by_new = (
            select(Appraisal.cycle_id)
            .join(AppraisalCycle, AppraisalCycle.id == Appraisal.cycle_id)
            .where(
                Appraisal.org_id == self._org,
                Appraisal.profile_id == profile_id,
                Appraisal.manager_user_id == manager_user_id,
                Appraisal.status.in_(OPEN),
                AppraisalCycle.status != CycleStatus.CLOSED,
            )
        )
        result = await self._db.execute(
            update(item)
            .where(
                item.org_id == self._org,
                item.profile_id == profile_id,
                item.status == FeedbackStatus.OPEN,
                item.manager_user_id != manager_user_id,
                item.cycle_id.in_(scored_by_new),
            )
            .values(manager_user_id=manager_user_id)
        )
        return rowcount(result)
