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

"""Where an item stands against the person's local day (pure, no I/O)."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, tzinfo
from enum import StrEnum


class DueBucket(StrEnum):
    """Which part of the message an item belongs to."""

    OVERDUE = "overdue"
    TODAY = "today"
    SOON = "soon"


@dataclass(frozen=True)
class LocalDay:
    """The person's local date and its bounds in their zone."""

    day: date
    zone: tzinfo
    start: datetime
    end: datetime

    @classmethod
    def of(cls, day: date, zone: tzinfo) -> "LocalDay":
        """The local day ``day`` in ``zone``, midnight to midnight."""
        start = datetime.combine(day, time(), tzinfo=zone)
        end = datetime.combine(day + timedelta(days=1), time(), tzinfo=zone)
        return cls(day=day, zone=zone, start=start, end=end)


def bucket(due_at: datetime, local: LocalDay) -> DueBucket:
    """Overdue means due before the local day began; after it ended is soon."""
    if due_at < local.start:
        return DueBucket.OVERDUE
    return DueBucket.TODAY if due_at < local.end else DueBucket.SOON


def due_words(due_at: datetime, local: LocalDay) -> str:
    """ "overdue by 3d", "today", "tomorrow" or "in 2d", counted in local dates."""
    days = (due_at.astimezone(local.zone).date() - local.day).days
    if days < 0:
        return f"overdue by {-days}d"
    if days == 0:
        return "today"
    return "tomorrow" if days == 1 else f"in {days}d"
