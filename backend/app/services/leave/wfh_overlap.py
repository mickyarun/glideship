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

"""How much of a WFH booking approved time off took over (pure, no I/O).

Leave can land on a WFH day and both rows stay, so cancelling the leave
brings the WFH back. A day taken over wasn't WFH, so the allowance and the
reports leave it out. Pending leave changes nothing until it's approved.
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.models.leave_request import HalfDay, LeaveKind, LeaveRequest, LeaveStatus
from app.services.leave.calendar_math import HALF_DAY, days_by_month, halves, iter_dates

TIME_OFF = (LeaveKind.LEAVE, LeaveKind.OPTIONAL_HOLIDAY)
ZERO = Decimal("0")


@dataclass(frozen=True)
class HeldDays:
    """The days a WFH being changed holds before the change."""

    start: date
    end: date
    half_day: HalfDay


def already_held(
    clash: LeaveRequest, held: HeldDays, start: date, end: date, half_day: HalfDay
) -> bool:
    """True when ``clash`` is time off only on days and halves the WFH already held.

    That time off landed on the WFH, so keeping those days isn't new WFH on leave.
    """
    if clash.kind not in TIME_OFF:
        return False
    inside = held.start <= max(clash.start_date, start) and min(clash.end_date, end) <= held.end
    return inside and halves(clash.half_day) & halves(half_day) <= halves(held.half_day)


def approved_time_off(requests: Sequence[LeaveRequest]) -> list[LeaveRequest]:
    """The requests that can take over a WFH day."""
    return [r for r in requests if r.kind in TIME_OFF and r.status == LeaveStatus.APPROVED]


def taken_over_by_month(
    wfh: LeaveRequest,
    time_off: Sequence[LeaveRequest],
    start: date,
    end: date,
    *,
    working_days: Collection[int],
    holidays: Mapping[date, str],
) -> dict[tuple[int, int], Decimal]:
    """Days of ``wfh`` inside ``start..end`` that one person's ``time_off`` covers.

    Split by ``(year, month)``; each half of a day counts 0.5. Weekends and
    holidays were never counted as WFH, so they aren't taken back.
    """
    out: dict[tuple[int, int], Decimal] = {}
    for day in iter_dates(max(wfh.start_date, start), min(wfh.end_date, end)):
        if day.weekday() not in working_days or day in holidays:
            continue
        off: set[HalfDay] = set()
        for request in time_off:
            if request.start_date <= day <= request.end_date:
                off |= halves(request.half_day)
        lost = len(halves(wfh.half_day) & off) * HALF_DAY
        if lost:
            key = (day.year, day.month)
            out[key] = out.get(key, ZERO) + lost
    return out


def replaced_between(
    wfh: LeaveRequest,
    time_off: Sequence[LeaveRequest],
    start: date,
    end: date,
    *,
    working_days: Collection[int],
    holidays: Mapping[date, str],
) -> bool:
    """True when ``time_off`` covers everything ``wfh`` books inside ``start..end``."""
    first, last = max(wfh.start_date, start), min(wfh.end_date, end)
    booked = days_by_month(first, last, wfh.half_day, working_days=working_days, holidays=holidays)
    taken = taken_over_by_month(
        wfh, time_off, first, last, working_days=working_days, holidays=holidays
    )
    return bool(booked) and booked == taken
