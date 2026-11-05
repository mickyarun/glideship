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

"""How much of a WFH booking approved time off takes over (pure)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models.leave_request import HalfDay, LeaveKind, LeaveRequest, LeaveStatus
from app.services.leave.wfh_overlap import approved_time_off, taken_over_by_month

MON, TUE, THU, FRI = date(2026, 6, 1), date(2026, 6, 2), date(2026, 6, 4), date(2026, 6, 5)
SAT = date(2026, 6, 6)
AM, PM = HalfDay.FIRST_HALF, HalfDay.SECOND_HALF
WEEKDAYS = (0, 1, 2, 3, 4)
JUNE = (2026, 6)


def _request(
    start: date,
    end: date,
    *,
    kind: LeaveKind = LeaveKind.LEAVE,
    half_day: HalfDay = HalfDay.NONE,
    status: LeaveStatus = LeaveStatus.APPROVED,
) -> LeaveRequest:
    return LeaveRequest(
        kind=kind, start_date=start, end_date=end, half_day=half_day, status=status
    )


def _wfh(start: date = MON, end: date = FRI, half_day: HalfDay = HalfDay.NONE) -> LeaveRequest:
    return _request(start, end, kind=LeaveKind.WFH, half_day=half_day)


def _taken(
    wfh: LeaveRequest,
    *time_off: LeaveRequest,
    start: date = MON,
    end: date = SAT,
    holidays: dict[date, str] | None = None,
) -> dict[tuple[int, int], Decimal]:
    return taken_over_by_month(
        wfh, time_off, start, end, working_days=WEEKDAYS, holidays=holidays or {}
    )


def test_a_full_day_of_leave_takes_one_day() -> None:
    assert _taken(_wfh(), _request(THU, THU)) == {JUNE: Decimal("1")}


def test_nothing_is_taken_without_an_overlap() -> None:
    assert _taken(_wfh(MON, TUE), _request(THU, FRI)) == {}


def test_half_days_count_half_and_only_where_they_overlap() -> None:
    assert _taken(_wfh(), _request(THU, THU, half_day=AM)) == {JUNE: Decimal("0.5")}
    assert _taken(_wfh(THU, THU, AM), _request(THU, THU, half_day=AM)) == {JUNE: Decimal("0.5")}
    assert _taken(_wfh(THU, THU, AM), _request(THU, THU, half_day=PM)) == {}
    assert _taken(_wfh(THU, THU, AM), _request(THU, THU)) == {JUNE: Decimal("0.5")}


def test_two_half_days_of_leave_take_the_whole_day() -> None:
    both = (_request(THU, THU, half_day=AM), _request(THU, THU, half_day=PM))
    assert _taken(_wfh(), *both) == {JUNE: Decimal("1")}


def test_days_that_were_never_wfh_are_not_taken_back() -> None:
    assert _taken(_wfh(THU, SAT), _request(FRI, SAT)) == {JUNE: Decimal("1")}
    assert _taken(_wfh(), _request(THU, THU), holidays={THU: "Onam"}) == {}


def test_only_days_inside_the_range_count() -> None:
    assert _taken(_wfh(), _request(MON, FRI), start=TUE, end=THU) == {JUNE: Decimal("3")}


def test_days_are_split_by_month() -> None:
    wfh = _wfh(date(2026, 6, 29), date(2026, 7, 3))
    leave = _request(date(2026, 6, 30), date(2026, 7, 1))
    taken = _taken(wfh, leave, start=date(2026, 6, 1), end=date(2026, 7, 31))
    assert taken == {JUNE: Decimal("1"), (2026, 7): Decimal("1")}


def test_only_approved_time_off_can_take_over() -> None:
    approved = _request(THU, THU)
    holiday = _request(FRI, FRI, kind=LeaveKind.OPTIONAL_HOLIDAY)
    rows = [
        approved,
        holiday,
        _request(MON, MON, status=LeaveStatus.PENDING),
        _request(TUE, TUE, status=LeaveStatus.REJECTED),
        _wfh(),
    ]
    assert approved_time_off(rows) == [approved, holiday]
