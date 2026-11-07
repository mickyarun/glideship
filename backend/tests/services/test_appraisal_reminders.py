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

"""The reminder schedule, working-day counting, feedback periods and DM wording."""

from datetime import date

import pytest

from app.models.appraisal_enums import CheckInCadence, FeedbackCadence
from app.services.appraisals.cadence import feedback_periods
from app.services.appraisals.reminder_text import (
    FeedbackBatch,
    check_in_ready_text,
    feedback_line,
    feedback_text,
    hr_overdue_text,
    period_label,
    short_date,
)
from app.services.appraisals.reminders import Moment, Schedule, hr_list_today, moment
from app.services.appraisals.work_calendar import WorkCalendar

WEEK = WorkCalendar()
TUE_10_NOV = date(2026, 11, 10)
SCHEDULE = Schedule(offsets=(-3, 0, 2), overdue_nudge=True, hr_list=True, hr_offset=3)


def test_shift_skips_weekends_and_holidays() -> None:
    assert WEEK.shift(TUE_10_NOV, -3) == date(2026, 11, 5)  # Thu, over the weekend
    assert WEEK.shift(TUE_10_NOV, 2) == date(2026, 11, 12)
    holiday = WorkCalendar(holidays=frozenset({date(2026, 11, 11)}))
    assert holiday.shift(TUE_10_NOV, 2) == date(2026, 11, 13)


def test_shift_by_zero_rolls_a_weekend_due_date_to_monday() -> None:
    assert WEEK.shift(date(2026, 11, 7), 0) == date(2026, 11, 9)
    assert WEEK.shift(TUE_10_NOV, 0) == TUE_10_NOV


def test_a_six_day_week_counts_saturdays() -> None:
    six = WorkCalendar(working_days=frozenset({0, 1, 2, 3, 4, 5}))
    assert six.shift(TUE_10_NOV, -3) == date(2026, 11, 6)


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (date(2026, 11, 2), Moment.OPENS),
        (date(2026, 11, 5), Moment.BEFORE),
        (TUE_10_NOV, Moment.DUE),
        (date(2026, 11, 12), Moment.AFTER),
        (date(2026, 11, 6), None),
        (date(2026, 11, 13), None),
    ],
)
def test_moment_follows_the_schedule(today: date, expected: Moment | None) -> None:
    assert moment(today, date(2026, 11, 2), TUE_10_NOV, SCHEDULE, WEEK) is expected


def test_no_overdue_nudge_means_nothing_after_the_due_date() -> None:
    quiet = Schedule(offsets=(-3, 0, 2), overdue_nudge=False, hr_list=True, hr_offset=3)
    assert moment(date(2026, 11, 12), None, TUE_10_NOV, quiet, WEEK) is None
    assert moment(TUE_10_NOV, None, TUE_10_NOV, quiet, WEEK) is Moment.DUE


def test_hr_list_goes_once_on_its_offset_and_only_when_switched_on() -> None:
    assert hr_list_today(date(2026, 11, 13), TUE_10_NOV, SCHEDULE, WEEK)
    assert not hr_list_today(date(2026, 11, 12), TUE_10_NOV, SCHEDULE, WEEK)
    off = Schedule(offsets=(), overdue_nudge=True, hr_list=False, hr_offset=3)
    assert not hr_list_today(date(2026, 11, 13), TUE_10_NOV, off, WEEK)


def test_quarterly_feedback_leaves_the_last_quarter_to_the_review() -> None:
    half = feedback_periods(date(2026, 7, 1), date(2026, 12, 31), FeedbackCadence.QUARTERLY)
    assert half == [(date(2026, 7, 1), date(2026, 9, 30))]
    year = feedback_periods(date(2027, 1, 1), date(2027, 12, 31), FeedbackCadence.QUARTERLY)
    assert [p[0].month for p in year] == [1, 4, 7]


def test_monthly_feedback_answers_every_month_and_in_review_has_none() -> None:
    quarter = (date(2026, 10, 1), date(2026, 12, 31))
    assert len(feedback_periods(*quarter, FeedbackCadence.MONTHLY)) == 3
    assert feedback_periods(*quarter, FeedbackCadence.IN_REVIEW) == []


def test_wording_carries_counts_and_dates_only() -> None:
    batch = FeedbackBatch(date(2027, 1, 1), CheckInCadence.QUARTERLY, date(2027, 4, 10), 6, 2)
    assert feedback_line(Moment.OPENS, batch) == (
        "Q1 2027 feedback is open for your 6 reports. Due Sat 10 Apr."
    )
    assert feedback_line(Moment.BEFORE, batch) == "Q1 2027 feedback due Sat 10 Apr: 2 of 6 done."
    assert feedback_line(Moment.DUE, batch) == "Q1 2027 feedback is due today: 2 of 6 done."
    assert feedback_line(Moment.AFTER, batch).startswith("Q1 2027 feedback was due")
    text = feedback_text(["a", "b"], "https://app.test/")
    assert text == "a\nb\n<https://app.test/appraisals/team|Open team>"


def test_labels_and_other_messages() -> None:
    assert period_label(date(2026, 10, 1), CheckInCadence.MONTHLY) == "October"
    assert short_date(TUE_10_NOV) == "Tue 10 Nov"
    assert "October check-in is ready" in check_in_ready_text(["October"], "https://a.test")
    hr = hr_overdue_text([("Ravi", 2), ("", 1)], "https://a.test")
    assert hr.startswith("Manager feedback still open past its due date: Ravi 2, Unnamed 1.")
