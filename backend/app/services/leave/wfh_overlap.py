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
from datetime import date
from decimal import Decimal

from app.models.leave_request import HalfDay, LeaveKind, LeaveRequest, LeaveStatus
from app.services.leave.calendar_math import HALF_DAY, halves, iter_dates

TIME_OFF = (LeaveKind.LEAVE, LeaveKind.OPTIONAL_HOLIDAY)
ZERO = Decimal("0")


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
