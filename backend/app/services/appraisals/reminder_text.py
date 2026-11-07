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

"""The words of appraisal reminder DMs (pure).

DMs carry counts, dates and links only: never a report's name, a band or
a note. HR's overdue list names managers, because chasing them is the
point of it.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from app.models.appraisal_enums import CheckInCadence
from app.services.appraisals.reminders import Moment

TEAM_PATH = "/appraisals/team"
MY_MONTH_PATH = "/appraisals"
CYCLES_PATH = "/appraisals/cycles"


@dataclass(frozen=True)
class FeedbackBatch:
    """One manager's feedback items for one period."""

    period_start: date
    cadence: CheckInCadence
    due_on: date
    total: int
    done: int


def short_date(day: date) -> str:
    """Like "Fri 10 Apr"."""
    return f"{day:%a} {day.day} {day:%b}"


def period_label(start: date, cadence: CheckInCadence) -> str:
    """ "October" for a month, "Q4 2026" for a quarter."""
    if cadence is CheckInCadence.QUARTERLY:
        return f"Q{(start.month - 1) // 3 + 1} {start.year}"
    return f"{start:%B}"


def _link(base_url: str, path: str, label: str) -> str:
    return f"<{base_url.rstrip('/')}{path}|{label}>"


def feedback_line(moment: Moment, batch: FeedbackBatch) -> str:
    """One period's line in a manager's reminder."""
    label = period_label(batch.period_start, batch.cadence)
    due = short_date(batch.due_on)
    progress = f"{batch.done} of {batch.total} done"
    if moment is Moment.OPENS:
        people = "report" if batch.total == 1 else "reports"
        return f"{label} feedback is open for your {batch.total} {people}. Due {due}."
    if moment is Moment.BEFORE:
        return f"{label} feedback due {due}: {progress}."
    if moment is Moment.DUE:
        return f"{label} feedback is due today: {progress}."
    return f"{label} feedback was due {due}: {progress}."


def feedback_text(lines: Sequence[str], base_url: str) -> str:
    """A manager's whole reminder: every period due today, one link."""
    return "\n".join([*lines, _link(base_url, TEAM_PATH, "Open team")])


def check_in_ready_text(labels: Sequence[str], base_url: str) -> str:
    """The person's "your month is ready" message."""
    which = " and ".join(labels)
    return (
        f"Your {which} check-in is ready. Add anything Glideship missed. "
        f"{_link(base_url, MY_MONTH_PATH, 'Open My month')}"
    )


def hr_overdue_text(managers: Sequence[tuple[str, int]], base_url: str) -> str:
    """HR's one list: managers with feedback still open past its due date."""
    listed = ", ".join(f"{name or 'Unnamed'} {count}" for name, count in managers)
    return (
        f"Manager feedback still open past its due date: {listed}. "
        f"{_link(base_url, CYCLES_PATH, 'Open cycles')}"
    )
