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

"""Due dates for check-ins and manager notes, counted in working days, and lateness."""

from datetime import UTC, date, datetime

from app.services.appraisals.due_dates import (
    check_in_due,
    is_late,
    may_change_after_send,
    note_due,
)
from app.services.appraisals.work_calendar import WorkCalendar

WEEK = WorkCalendar()
SENT = datetime(2026, 11, 4, 9, tzinfo=UTC)


def test_a_check_in_is_due_five_working_days_after_its_month_skipping_weekends() -> None:
    # October ends on Saturday the 31st: Mon 2 to Fri 6 Nov are the five days.
    assert check_in_due(date(2026, 10, 31), date(2026, 11, 2), 5, WEEK) == date(2026, 11, 6)
    # November ends on a Monday: Tue to Fri, then the next Monday.
    assert check_in_due(date(2026, 11, 30), date(2026, 12, 1), 5, WEEK) == date(2026, 12, 7)


def test_holidays_on_the_persons_calendar_push_the_date_out() -> None:
    holiday = WorkCalendar(holidays=frozenset({date(2026, 11, 3)}))
    assert check_in_due(date(2026, 10, 31), date(2026, 11, 2), 5, holiday) == date(2026, 11, 9)


def test_a_check_in_opened_after_its_usual_date_gets_a_fresh_window() -> None:
    # A cycle opened on Mon 16 Nov: October's check-in would already be late.
    assert check_in_due(date(2026, 10, 31), date(2026, 11, 16), 5, WEEK) == date(2026, 11, 23)


def test_a_note_is_due_five_working_days_after_the_check_in_is_sent() -> None:
    # Sent on Thursday 5 Nov: Fri, Mon, Tue, Wed, Thu.
    assert note_due(date(2026, 11, 5), 5, WEEK) == date(2026, 11, 12)
    # Sent on a Saturday: counting starts on the Monday.
    assert note_due(date(2026, 11, 7), 5, WEEK) == date(2026, 11, 13)


def test_late_means_past_due_and_not_sent() -> None:
    due = date(2026, 11, 6)
    assert not is_late(due, None, date(2026, 11, 6))
    assert is_late(due, None, date(2026, 11, 7))
    assert not is_late(due, SENT, date(2026, 11, 30))
    # Nothing is due yet (a note whose check-in isn't sent): never late.
    assert not is_late(None, None, date(2026, 12, 31))


def test_a_sent_check_in_can_change_until_its_due_date() -> None:
    due = date(2026, 11, 6)
    assert may_change_after_send(due, None, date(2026, 12, 1))
    assert may_change_after_send(due, SENT, due)
    assert not may_change_after_send(due, SENT, date(2026, 11, 9))
    # Sent before it had a due date: still open to changes.
    assert may_change_after_send(None, SENT, date(2026, 11, 9))
