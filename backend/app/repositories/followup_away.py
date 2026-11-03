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

"""Who is away on a given day, for skipping their daily follow-ups DM.

Away means an approved full-day leave or optional holiday covering the day
(working from home and half days don't count), or a mandatory holiday on
the person's own leave policy (the org default when they have none).
"""

import uuid
from collections.abc import Collection
from datetime import date

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.employee_profile import EmployeeProfile
from app.models.leave_policy import LeavePolicy
from app.models.leave_request import HalfDay, LeaveKind, LeaveRequest, LeaveStatus
from app.models.policy_holiday import HolidayKind, PolicyHoliday
from app.models.user import OrgToUser


class AwayRepository:
    """Leave and holidays in one org, read for daily messages."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        """Initialize the repository."""
        self._db = db
        self._org = org_id

    async def away_on(self, user_ids: Collection[uuid.UUID], day: date) -> set[uuid.UUID]:
        """The people in ``user_ids`` who are on leave or on a holiday on ``day``."""
        if not user_ids:
            return set()
        return await self._on_leave(user_ids, day) | await self._on_holiday(user_ids, day)

    async def _on_leave(self, user_ids: Collection[uuid.UUID], day: date) -> set[uuid.UUID]:
        rows = await self._db.scalars(
            select(LeaveRequest.user_id).where(
                LeaveRequest.org_id == self._org,
                LeaveRequest.user_id.in_(list(user_ids)),
                LeaveRequest.status == LeaveStatus.APPROVED,
                LeaveRequest.kind != LeaveKind.WFH,
                LeaveRequest.half_day == HalfDay.NONE,
                LeaveRequest.start_date <= day,
                LeaveRequest.end_date >= day,
            )
        )
        return set(rows.all())

    async def _on_holiday(self, user_ids: Collection[uuid.UUID], day: date) -> set[uuid.UUID]:
        default = aliased(LeavePolicy)
        policy_id = func.coalesce(EmployeeProfile.leave_policy_id, default.id)
        rows = await self._db.scalars(
            select(OrgToUser.user_id)
            .outerjoin(
                EmployeeProfile,
                and_(
                    EmployeeProfile.org_id == self._org,
                    EmployeeProfile.user_id == OrgToUser.user_id,
                ),
            )
            .outerjoin(default, and_(default.org_id == self._org, default.is_default.is_(True)))
            .join(
                PolicyHoliday,
                and_(
                    PolicyHoliday.policy_id == policy_id,
                    PolicyHoliday.date == day,
                    PolicyHoliday.kind == HolidayKind.MANDATORY,
                ),
            )
            .where(OrgToUser.org_id == self._org, OrgToUser.user_id.in_(list(user_ids)))
        )
        return set(rows.all())
