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

"""How many working days someone was available in a check-in period.

Shown on the check-in ("17 of 21 days · 4 on leave") so a short month
reads as a short month, never as low output. WFH days count as available.
"""

import uuid
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee_profile import EmployeeProfile
from app.models.leave_request import HalfDay, LeaveKind, LeaveStatus
from app.repositories.leave_request import LeaveRequestRepository
from app.services.leave.calendar_math import count_days
from app.services.leave.policies import mandatory_holidays, resolve_member_policy

# Requests that take someone away from work. WFH doesn't.
AWAY_KINDS = (LeaveKind.LEAVE, LeaveKind.OPTIONAL_HOLIDAY)


@dataclass(frozen=True)
class Absence:
    """One approved absence, as booked."""

    start: date
    end: date
    half_day: HalfDay = HalfDay.NONE


@dataclass(frozen=True)
class Availability:
    """Working days in the period while employed, and how many of them free."""

    working_days: int
    available_days: Decimal


def availability(
    start: date,
    end: date,
    *,
    working_days: Collection[int],
    holidays: Mapping[date, str],
    absences: Sequence[Absence],
    joined: date | None = None,
    exited: date | None = None,
) -> Availability:
    """Count the period's working days and subtract absences (pure).

    Only days while employed count, so a mid-month joiner's check-in is
    measured against the days they were here. A half day only applies to a
    one-day booking, as in leave balances.
    """
    first = max(start, joined) if joined else start
    last = min(end, exited) if exited else end
    if first > last:
        return Availability(working_days=0, available_days=Decimal("0"))
    total = count_days(first, last, HalfDay.NONE, working_days=working_days, holidays=holidays)
    away = Decimal("0")
    for absence in absences:
        clip_start, clip_end = max(first, absence.start), min(last, absence.end)
        if clip_start > clip_end:
            continue
        # A half day only survives when the booking itself was one day.
        half = absence.half_day if absence.start == absence.end else HalfDay.NONE
        away += count_days(
            clip_start, clip_end, half, working_days=working_days, holidays=holidays
        ).days
    days = int(total.days)
    return Availability(working_days=days, available_days=max(Decimal("0"), total.days - away))


async def availability_for(
    db: AsyncSession, org_id: uuid.UUID, profile: EmployeeProfile, start: date, end: date
) -> Availability:
    """The person's availability under their leave policy and approved leave."""
    member = await resolve_member_policy(db, org_id, profile.user_id)
    holidays = await mandatory_holidays(db, member.policy, start, end)
    requests = await LeaveRequestRepository(db, org_id=org_id).active_between(
        [profile.user_id], start, end, kinds=AWAY_KINDS
    )
    absences = [
        Absence(r.start_date, r.end_date, r.half_day)
        for r in requests
        if r.status is LeaveStatus.APPROVED
    ]
    return availability(
        start,
        end,
        working_days=member.policy.working_days,
        holidays=holidays,
        absences=absences,
        joined=profile.date_of_joining,
        exited=profile.date_of_exit,
    )
