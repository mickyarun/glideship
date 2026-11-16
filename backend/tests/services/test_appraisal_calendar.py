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

"""Cadence rules, period maths, check-in closing days and availability (pure)."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.models.appraisal import Appraisal
from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_enums import (
    AppraisalStatus,
    CheckInCadence,
    FeedbackCadence,
    ReviewPeriod,
)
from app.models.employee_profile import EmployeeProfile
from app.models.leave_request import HalfDay
from app.services.appraisals.availability import Absence, availability
from app.services.appraisals.cadence import cadence_error, period_after, slices
from app.services.appraisals.check_in_scheduler import Tick, is_empty, latest_ended, should_open
from app.services.appraisals.cycles import default_name, enrolment_cutoff
from tests.integration.appraisal_support import cycle_row

Q, H, Y = ReviewPeriod.QUARTERLY, ReviewPeriod.HALF_YEARLY, ReviewPeriod.YEARLY
M, QC = CheckInCadence.MONTHLY, CheckInCadence.QUARTERLY
WEEK = [0, 1, 2, 3, 4]


@pytest.mark.parametrize(
    ("review", "checkins", "feedback", "ok"),
    [
        (Q, M, FeedbackCadence.MONTHLY, True),
        (Q, M, FeedbackCadence.IN_REVIEW, True),
        (Q, M, FeedbackCadence.QUARTERLY, False),
        (Q, QC, FeedbackCadence.IN_REVIEW, False),
        (H, M, FeedbackCadence.QUARTERLY, True),
        (H, QC, FeedbackCadence.QUARTERLY, True),
        (H, QC, FeedbackCadence.MONTHLY, False),
        (H, M, FeedbackCadence.IN_REVIEW, False),
        (Y, QC, FeedbackCadence.QUARTERLY, True),
    ],
)
def test_cadence_rules(
    review: ReviewPeriod, checkins: CheckInCadence, feedback: FeedbackCadence, ok: bool
) -> None:
    assert (cadence_error(review, checkins, feedback) is None) is ok


def test_slices_cover_the_period_month_by_month() -> None:
    assert slices(date(2026, 10, 1), date(2026, 12, 31), 1) == [
        (date(2026, 10, 1), date(2026, 10, 31)),
        (date(2026, 11, 1), date(2026, 11, 30)),
        (date(2026, 12, 1), date(2026, 12, 31)),
    ]
    assert slices(date(2026, 1, 1), date(2026, 6, 30), 3)[1] == (
        date(2026, 4, 1),
        date(2026, 6, 30),
    )


def test_next_period_follows_the_last_cycle_or_today() -> None:
    assert period_after(date(2026, 12, 31), date(2026, 11, 4), Q) == (
        date(2027, 1, 1),
        date(2027, 3, 31),
    )
    assert period_after(None, date(2026, 11, 4), Q) == (date(2026, 10, 1), date(2026, 12, 31))
    assert period_after(None, date(2026, 11, 4), H) == (date(2026, 7, 1), date(2026, 12, 31))


def test_cycle_names_and_cut_off() -> None:
    assert default_name(Q, date(2026, 10, 1)) == "Q4 2026"
    assert default_name(H, date(2027, 1, 1)) == "H1 2027"
    assert default_name(Y, date(2027, 1, 1)) == "2027"
    assert enrolment_cutoff(date(2026, 10, 1), date(2026, 12, 31)) == date(2026, 10, 31)


def _tick(today: date, *, working: bool = True) -> Tick:
    return Tick(
        now=datetime(today.year, today.month, today.day, 6, tzinfo=UTC),
        today=today,
        working=working,
        zone=UTC,
    )


def test_only_the_latest_ended_period_opens() -> None:
    cycle = cycle_row(None)  # type: ignore[arg-type]
    assert latest_ended(cycle, date(2026, 10, 31)) is None
    assert latest_ended(cycle, date(2026, 11, 2)) == (date(2026, 10, 1), date(2026, 10, 31))
    # Enrolled late, in December: only November opens, October isn't backfilled.
    assert latest_ended(cycle, date(2026, 12, 2)) == (date(2026, 11, 1), date(2026, 11, 30))


def test_when_a_check_in_opens() -> None:
    cycle = cycle_row(None)  # type: ignore[arg-type]
    appraisal = Appraisal(status=AppraisalStatus.ENROLLED)
    profile = EmployeeProfile()
    october = (date(2026, 10, 1), date(2026, 10, 31))
    december = (date(2026, 12, 1), date(2026, 12, 31))
    assert should_open(cycle, appraisal, profile, october, _tick(date(2026, 11, 2)))
    assert not should_open(
        cycle, appraisal, profile, october, _tick(date(2026, 11, 2), working=False)
    )
    profile.date_of_joining = date(2026, 11, 2)
    assert not should_open(cycle, appraisal, profile, october, _tick(date(2026, 11, 2)))
    profile.date_of_joining, profile.date_of_exit = None, date(2026, 9, 30)
    assert not should_open(cycle, appraisal, profile, october, _tick(date(2026, 11, 2)))
    profile.date_of_exit = None
    # The last month would close straight away once the self-review is due.
    assert not should_open(cycle, appraisal, profile, december, _tick(cycle.self_due))
    appraisal.status = AppraisalStatus.WITHDRAWN
    assert not should_open(cycle, appraisal, profile, october, _tick(date(2026, 11, 2)))


def test_stale_tags_dont_make_a_check_in_count_as_started() -> None:
    check_in = AppraisalCheckIn(
        fact_refs=[{"id": "live"}], fact_tags={"gone": {"heading": "team"}}
    )
    assert is_empty(check_in, set(), 0)
    check_in.fact_tags = {"live": {"heading": "team"}}
    assert not is_empty(check_in, set(), 0)
    assert not is_empty(AppraisalCheckIn(fact_refs=[], fact_tags={}), {"link"}, 0)


OCT = (date(2026, 10, 1), date(2026, 10, 31))


def test_october_has_22_working_days_and_leave_comes_off() -> None:
    full = availability(*OCT, working_days=WEEK, holidays={}, absences=[])
    assert (full.working_days, full.available_days) == (22, Decimal(22))
    away = availability(
        *OCT,
        working_days=WEEK,
        holidays={},
        absences=[Absence(date(2026, 10, 19), date(2026, 10, 25))],
    )
    assert away.available_days == Decimal(17)  # Mon–Fri off; the weekend wasn't working


def test_holidays_and_half_days() -> None:
    holiday = {date(2026, 10, 2): "Gandhi Jayanti"}
    result = availability(
        *OCT,
        working_days=WEEK,
        holidays=holiday,
        absences=[Absence(date(2026, 10, 6), date(2026, 10, 6), HalfDay.FIRST_HALF)],
    )
    assert (result.working_days, result.available_days) == (21, Decimal("20.5"))


def test_joining_and_leaving_mid_month() -> None:
    joined = availability(
        *OCT, working_days=WEEK, holidays={}, absences=[], joined=date(2026, 10, 19)
    )
    assert joined.working_days == 10
    left = availability(
        *OCT, working_days=WEEK, holidays={}, absences=[], exited=date(2026, 10, 9)
    )
    assert left.working_days == 7
    never = availability(
        *OCT, working_days=WEEK, holidays={}, absences=[], joined=date(2026, 11, 2)
    )
    assert (never.working_days, never.available_days) == (0, Decimal(0))


def test_leave_spilling_past_the_month_counts_only_inside_it() -> None:
    result = availability(
        *OCT,
        working_days=WEEK,
        holidays={},
        absences=[Absence(date(2026, 10, 29), date(2026, 11, 4))],
    )
    assert result.available_days == Decimal(20)
