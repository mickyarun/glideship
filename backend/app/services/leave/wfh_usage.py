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

"""How much WFH a member has used, and whether a new request is auto-approved."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.leave_policy import LeavePolicy
from app.models.leave_request import HalfDay, LeaveKind, LeaveRequest
from app.repositories.leave_request import LeaveRequestRepository
from app.repositories.leave_type import LeaveTypeRepository
from app.services.leave.calendar_math import days_by_month
from app.services.leave.month_usage import month_span, requested_by_month
from app.services.leave.policies import mandatory_holidays
from app.services.leave.type_privacy import visible
from app.services.leave.wfh_overlap import approved_time_off, taken_over_by_month
from app.services.leave.wfh_policy import Month, needs_approval

ZERO = Decimal("0")


async def _not_hidden(
    db: AsyncSession, org_id: uuid.UUID, time_off: list[LeaveRequest]
) -> list[LeaveRequest]:
    """The requests whose type anyone may see."""
    types = await LeaveTypeRepository(db, org_id=org_id).by_ids(
        {r.leave_type_id for r in time_off if r.leave_type_id}
    )
    return visible(
        time_off,
        lambda r: types.get(r.leave_type_id) if r.leave_type_id else None,
        sees_all=False,
    )


async def wfh_days_by_month(
    db: AsyncSession,
    policy: LeavePolicy,
    user_id: uuid.UUID,
    start: date,
    end: date,
    *,
    sees_all: bool = True,
) -> dict[Month, Decimal]:
    """Approved + pending WFH working days per month across the months of a range.

    Days that approved time off took over don't count: they weren't WFH.
    With ``sees_all`` off, a hidden type's days stay WFH, so the figure can't
    give that leave away (see type_privacy).
    """
    first, last = month_span(start, end)
    rows = await LeaveRequestRepository(db, org_id=policy.org_id).active_between(
        [user_id], first, last
    )
    time_off = approved_time_off(rows)
    if not sees_all:
        time_off = await _not_hidden(db, policy.org_id, time_off)
    holidays = await mandatory_holidays(db, policy, first, last)
    working_days = policy.working_days
    used: dict[Month, Decimal] = {}
    for wfh in (r for r in rows if r.kind == LeaveKind.WFH):
        booked = days_by_month(
            wfh.start_date,
            wfh.end_date,
            wfh.half_day,
            working_days=working_days,
            holidays=holidays,
        )
        taken = taken_over_by_month(
            wfh, time_off, first, last, working_days=working_days, holidays=holidays
        )
        for month, days in booked.items():
            used[month] = used.get(month, ZERO) + days - taken.get(month, ZERO)
    return used


async def wfh_auto_approved(
    db: AsyncSession,
    policy: LeavePolicy,
    user_id: uuid.UUID,
    start: date,
    end: date,
    half_day: HalfDay,
) -> bool:
    """True if the policy approves this WFH request without a manager."""
    requested = await requested_by_month(db, policy, start, end, half_day)
    already = await wfh_days_by_month(db, policy, user_id, start, end)
    return not needs_approval(
        policy.wfh_approval, policy.wfh_monthly_auto_days, already=already, requested=requested
    )
