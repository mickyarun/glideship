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
"""Who gets public holidays on their Google Calendar, and on which policy."""

import uuid
from collections.abc import Collection
from dataclasses import dataclass

from sqlalchemy import func, literal, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee_profile import EmployeeProfile, EmployeeStatus
from app.models.leave_policy import LeavePolicy
from app.models.user import User


@dataclass(frozen=True)
class CalendarPerson:
    """An employee whose calendar we write, and the policy whose holidays they get."""

    user_id: uuid.UUID
    email: str
    policy_id: uuid.UUID
    # Exited or switched off: their holidays come off the calendar.
    left: bool


class LeaveCalendarPeopleRepository:
    """Current employees with an email, scoped to one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        """Initialize the repository."""
        self._db = db
        self._org = org_id

    async def list_people(
        self,
        default_policy: LeavePolicy,
        *,
        policy_id: uuid.UUID | None = None,
        user_ids: Collection[uuid.UUID] | None = None,
    ) -> list[CalendarPerson]:
        """Employees with an email, on their policy (the default when unassigned).

        ``policy_id`` keeps only that policy's people. People who have left
        are listed only when named in ``user_ids``, so their holidays can be
        taken off once; otherwise only current employees.
        """
        policy = func.coalesce(EmployeeProfile.leave_policy_id, literal(default_policy.id))
        left = or_(EmployeeProfile.status == EmployeeStatus.EXITED, User.is_active.is_(False))
        stmt = (
            select(User.id, User.email, policy, left)
            .join(EmployeeProfile, EmployeeProfile.user_id == User.id)
            .where(
                EmployeeProfile.org_id == self._org,
                User.email.is_not(None),
                User.email != "",
            )
        )
        if policy_id is not None:
            stmt = stmt.where(policy == policy_id)
        if user_ids is not None:
            stmt = stmt.where(User.id.in_(user_ids))
        else:
            stmt = stmt.where(not_(left))
        return [CalendarPerson(*row) for row in (await self._db.execute(stmt)).all()]
