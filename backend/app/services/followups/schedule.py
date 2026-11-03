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

"""Whose follow-ups are due now, each in their own timezone (pure, no I/O)."""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from app.config import settings
from app.repositories.followup_settings import SubscriberRow
from app.services.followups.due_state import LocalDay
from app.services.followups.zone import default_zone
from app.services.quiz_schedule_math import resolve_zone
from app.services.scheduling.tick_loop import due_local_date

SATURDAY = 5


@dataclass(frozen=True)
class Subscriber:
    """One person with the follow-ups on in one org, and when they go out."""

    org_id: uuid.UUID
    user_id: uuid.UUID
    send_time: time
    timezone: str
    weekdays_only: bool

    @classmethod
    def of(cls, row: SubscriberRow) -> "Subscriber":
        """Their saved schedule, with the default zone where they never chose one."""
        return cls(
            org_id=row.org_id,
            user_id=row.user_id,
            send_time=row.send_time,
            timezone=row.saved_zone or default_zone(row.zone, row.org_id),
            weekdays_only=row.weekdays_only,
        )


def skips_day(weekdays_only: bool, day: date) -> bool:
    """Whether a weekdays-only schedule has no message on this local date."""
    return weekdays_only and day.weekday() >= SATURDAY


def due_day(person: Subscriber, now: datetime) -> LocalDay | None:
    """Their local day if their follow-ups are due at ``now``, else None.

    Due from their send time until ``FollowupsConfig.window_minutes`` later
    on the same local date, in their saved zone; weekends are skipped when
    they asked for weekdays only.
    """
    zone = resolve_zone(person.timezone)
    window = timedelta(minutes=settings.followups.window_minutes)
    day = due_local_date(now, zone, person.send_time, window=window)
    if day is None:
        return None
    return None if skips_day(person.weekdays_only, day) else LocalDay.of(day, zone)
