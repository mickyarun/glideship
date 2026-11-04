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

"""The holiday list: a whole leave year of one office's holidays.

Everyone reads their own policy's calendar. People who run leave (HR,
approvers, report viewers) may read any policy's, so they can answer
"is Friday off in London?" without opening settings.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permission_deps import PermissionSet
from app.models.leave_policy import LeavePolicy
from app.repositories.leave_policy import LeavePolicyRepository
from app.repositories.policy_holiday import PolicyHolidayRepository
from app.schemas.leave_holidays import HolidayCalendarOption, HolidayCalendarRead
from app.services.leave.calendar_math import leave_year_bounds, leave_year_by_label
from app.services.leave.errors import LeaveForbiddenError, LeaveNotFoundError
from app.services.leave.permissions import APPROVE, CONFIGURE, REPORTS
from app.services.leave.policies import resolve_member_policy, today_for
from app.services.leave.summary import holiday_schema, year_schema

SEES_EVERY_CALENDAR = (APPROVE, CONFIGURE, REPORTS)


def _option(policy: LeavePolicy) -> HolidayCalendarOption:
    return HolidayCalendarOption(id=policy.id, name=policy.name)


def _pick(
    own: LeavePolicy, visible: list[LeavePolicy], policy_id: uuid.UUID | None
) -> LeavePolicy:
    """The requested calendar from those the viewer may read."""
    if policy_id is None or policy_id == own.id:
        return own
    found = next((p for p in visible if p.id == policy_id), None)
    if found is None:
        raise LeaveNotFoundError("Holiday calendar not found.")
    return found


async def holiday_calendar(
    db: AsyncSession,
    org_id: uuid.UUID,
    viewer: uuid.UUID,
    perms: PermissionSet,
    policy_id: uuid.UUID | None,
    year: int | None,
) -> HolidayCalendarRead:
    """Holidays on one calendar (default: the viewer's) in one leave year.

    ``year`` is the leave-year label, as in the admin list; it defaults
    to the leave year containing today on that calendar.
    """
    own = (await resolve_member_policy(db, org_id, viewer)).policy
    if any(perms.has(p) for p in SEES_EVERY_CALENDAR):
        visible = await LeavePolicyRepository(db, org_id=org_id).list_ordered()
    elif policy_id not in (None, own.id):
        raise LeaveForbiddenError("You can only see your own office's holidays.")
    else:
        visible = [own]
    policy = _pick(own, visible, policy_id)
    today = today_for(policy)
    label = year if year is not None else leave_year_bounds(today, policy.year_start_month).label
    bounds = leave_year_by_label(label, policy.year_start_month)
    rows = await PolicyHolidayRepository(db, org_id=org_id).list_between(
        policy.id, bounds.start, bounds.end
    )
    return HolidayCalendarRead(
        calendar=_option(policy),
        calendars=[_option(p) for p in visible],
        leave_year=year_schema(bounds),
        today=today,
        holidays=[holiday_schema(h) for h in rows],
    )
