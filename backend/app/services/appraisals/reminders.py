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

"""When each appraisal reminder is due (pure, no I/O).

Every piece of work with an owner and a due date follows one schedule,
copied onto the cycle when it was created: a message when it opens, then
one on each reminder offset (working days from the due date, counted on
the recipient's calendar) while it isn't done. Offsets after the due date
only fire with the overdue nudge on. HR gets one list of what is still
open a set number of working days after the due date.
"""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from app.models.appraisal_cycle import AppraisalCycle
from app.services.appraisals.work_calendar import WorkCalendar


class Moment(StrEnum):
    """Which reminder in the schedule today is."""

    OPENS = "opens"
    BEFORE = "before"
    DUE = "due"
    AFTER = "after"


@dataclass(frozen=True)
class Schedule:
    """A cycle's reminder settings."""

    offsets: tuple[int, ...]
    overdue_nudge: bool
    hr_list: bool
    hr_offset: int

    @classmethod
    def of(cls, cycle: AppraisalCycle) -> "Schedule":
        """The schedule the cycle was created with."""
        return cls(
            offsets=tuple(sorted(cycle.reminder_offsets or [])),
            overdue_nudge=cycle.overdue_nudge,
            hr_list=cycle.hr_overdue_list,
            hr_offset=cycle.hr_overdue_offset,
        )


def moment(
    today: date,
    opened_on: date | None,
    due_on: date,
    schedule: Schedule,
    calendar: WorkCalendar,
) -> Moment | None:
    """Today's reminder for work that opened on ``opened_on`` and is due ``due_on``.

    The caller only asks while the work isn't done. The opening message
    wins over a reminder falling on the same day.
    """
    if opened_on == today:
        return Moment.OPENS
    for offset in schedule.offsets:
        if offset > 0 and not schedule.overdue_nudge:
            continue
        if calendar.shift(due_on, offset) == today:
            if offset < 0:
                return Moment.BEFORE
            return Moment.DUE if offset == 0 else Moment.AFTER
    return None


def hr_list_today(today: date, due_on: date, schedule: Schedule, calendar: WorkCalendar) -> bool:
    """Whether work due ``due_on`` and still open goes on HR's list today."""
    return schedule.hr_list and calendar.shift(due_on, schedule.hr_offset) == today
