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

"""When check-ins and manager notes are due, and when they are late (pure).

A check-in is due ``checkin_due_days`` working days after its period
ends, counted on the person's calendar. A manager note is due
``feedback_due_days`` working days after the check-in it answers is
sent, counted on the manager's; nothing is due before there is
something to answer. Both numbers come from the cycle, so HR can change
them for a cycle. The dates are worked out once, when the work opens (or
the check-in is sent), and stored: reminders and the to-do list read
them from the row, and a holiday added later doesn't move a date people
were already given.

Something is late when it is past its due date and not sent. Once sent,
the writer may still change it until the due date; the reader sees the
change, marked as edited after sending.
"""

from datetime import date, datetime

from app.services.appraisals.work_calendar import WorkCalendar


def check_in_due(period_end: date, opened_on: date, days: int, calendar: WorkCalendar) -> date:
    """The check-in's due date.

    One that opens after its usual due date (a cycle opened late, someone
    enrolled late) gets a fresh window from the day it opens, so nobody is
    handed a check-in that is already late.
    """
    usual = calendar.shift(period_end, days)
    return usual if usual >= opened_on else calendar.shift(opened_on, days)


def note_due(check_in_sent_on: date, days: int, calendar: WorkCalendar) -> date:
    """The manager note's due date, from the day the check-in was sent."""
    return calendar.shift(check_in_sent_on, days)


def is_late(due_on: date | None, sent_at: datetime | None, today: date) -> bool:
    """Past its due date and not sent."""
    return sent_at is None and due_on is not None and today > due_on


def may_change_after_send(due_on: date | None, sent_at: datetime | None, today: date) -> bool:
    """The writer may still change it: not sent yet, or sent and not past due.

    A note sent before its check-in was (so before it had a due date) stays
    open to changes until it gets one.
    """
    return sent_at is None or due_on is None or today <= due_on
