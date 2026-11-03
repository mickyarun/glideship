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

"""When one person's follow-ups are due: their own zone, time, and weekdays-only choice."""

import uuid
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.config import settings
from app.repositories.followup_settings import Subscriber
from app.services.followups.schedule import due_day, skips_day

# Wednesday 6 March 2030.
WEDNESDAY = date(2030, 3, 6)


def _person(
    *, send_time: time = time(8, 0), timezone: str = "Asia/Kolkata", weekdays_only: bool = True
) -> Subscriber:
    return Subscriber(
        org_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        send_time=send_time,
        timezone=timezone,
        weekdays_only=weekdays_only,
    )


def test_due_from_the_local_send_time_until_the_window_ends() -> None:
    person = _person()
    # 08:00 in Kolkata (UTC+5:30) is 02:30 UTC.
    at = datetime(2030, 3, 6, 2, 30, tzinfo=UTC)
    span = timedelta(minutes=settings.followups.window_minutes)
    assert due_day(person, at - timedelta(minutes=1)) is None
    local = due_day(person, at)
    assert local is not None and local.day == WEDNESDAY
    assert local.start == datetime(2030, 3, 6, tzinfo=ZoneInfo("Asia/Kolkata"))
    assert due_day(person, at + span - timedelta(minutes=1)) is not None
    assert due_day(person, at + span) is None


def test_two_people_in_different_zones_are_due_at_different_instants() -> None:
    london, kolkata = _person(timezone="Europe/London"), _person()
    at = datetime(2030, 3, 6, 2, 30, tzinfo=UTC)
    assert due_day(kolkata, at) is not None and due_day(london, at) is None
    assert due_day(london, datetime(2030, 3, 6, 8, 0, tzinfo=UTC)) is not None


def test_weekends_are_skipped_only_when_asked() -> None:
    # Saturday 9 March, 08:00 in London (GMT).
    saturday = datetime(2030, 3, 9, 8, 0, tzinfo=UTC)
    assert due_day(_person(timezone="Europe/London"), saturday) is None
    every_day = _person(timezone="Europe/London", weekdays_only=False)
    local = due_day(every_day, saturday)
    assert local is not None and local.day == date(2030, 3, 9)


def test_the_local_date_decides_the_weekday_not_utc() -> None:
    # Friday 23:30 UTC is already Saturday 05:00 in Kolkata.
    early = _person(send_time=time(5, 0))
    assert due_day(early, datetime(2030, 3, 8, 23, 30, tzinfo=UTC)) is None


def test_weekdays_only_skips_saturday_and_sunday_dates() -> None:
    assert skips_day(True, date(2030, 3, 9)) and skips_day(True, date(2030, 3, 10))
    assert not skips_day(True, WEDNESDAY) and not skips_day(False, date(2030, 3, 9))
