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

"""Working days on a person's leave policy, for counting reminder offsets.

A reminder "3 working days before" is counted on the recipient's own
policy: its working week and its mandatory holidays. People without a
policy of their own use the org's default one, and an org without any
policy works Monday to Friday.
"""

import uuid
from collections.abc import Collection
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.employee_profile import EmployeeProfileRepository
from app.repositories.leave_policy import LeavePolicyRepository
from app.repositories.policy_holiday import PolicyHolidayRepository

WEEKDAYS = frozenset({0, 1, 2, 3, 4})
# Holidays are loaded this far either side of today: reminder offsets are
# at most ten working days, and due dates up to 120 days after a period.
HOLIDAY_REACH = timedelta(days=180)


@dataclass(frozen=True)
class WorkCalendar:
    """One policy's working week and holidays (pure)."""

    working_days: frozenset[int] = WEEKDAYS
    holidays: frozenset[date] = field(default_factory=frozenset)

    def is_working(self, day: date) -> bool:
        """A day in the working week that isn't a holiday."""
        return day.weekday() in self.working_days and day not in self.holidays

    def shift(self, day: date, working_days: int) -> date:
        """The working day ``working_days`` after ``day`` (before, when negative).

        Zero gives ``day`` itself, or the next working day when it isn't one,
        so a due date on a weekend is reminded about on the Monday.
        """
        step = 1 if working_days >= 0 else -1
        current = day
        if working_days == 0:
            while not self.is_working(current):
                current += timedelta(days=1)
            return current
        left = abs(working_days)
        while left:
            current += timedelta(days=step)
            if self.is_working(current):
                left -= 1
        return current


@dataclass(frozen=True)
class Calendars:
    """Each person's calendar, and the org's default for everyone else."""

    default: WorkCalendar
    by_user: dict[uuid.UUID, WorkCalendar]

    def of(self, user_id: uuid.UUID) -> WorkCalendar:
        """The person's calendar."""
        return self.by_user.get(user_id, self.default)


async def load_calendars(
    db: AsyncSession, org_id: uuid.UUID, user_ids: Collection[uuid.UUID], today: date
) -> Calendars:
    """The calendars of ``user_ids``, with holidays around ``today``."""
    policies = LeavePolicyRepository(db, org_id=org_id)
    default_policy = await policies.get_default()
    profiles = await EmployeeProfileRepository(db, org_id=org_id).by_users(user_ids)
    own = {p.leave_policy_id for p in profiles.values() if p.leave_policy_id}
    rows = await policies.by_ids(own)
    if default_policy is not None:
        rows[default_policy.id] = default_policy
    holidays = await PolicyHolidayRepository(db, org_id=org_id).mandatory_between(
        list(rows), today - HOLIDAY_REACH, today + HOLIDAY_REACH
    )
    built = {
        policy.id: WorkCalendar(
            working_days=frozenset(policy.working_days or WEEKDAYS),
            holidays=frozenset(holidays.get(policy.id, set())),
        )
        for policy in rows.values()
    }
    default = built.get(default_policy.id) if default_policy else None
    fallback = default or WorkCalendar()
    by_user = {
        user_id: built.get(profile.leave_policy_id, fallback)
        if profile.leave_policy_id
        else fallback
        for user_id, profile in profiles.items()
    }
    return Calendars(default=fallback, by_user=by_user)
