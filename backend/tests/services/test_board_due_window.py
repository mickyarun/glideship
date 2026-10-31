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


"""When an org's due reminders fire: the configured window, its edges, and DST."""

import uuid
from datetime import UTC, date, datetime, timedelta

from app.config import settings
from app.repositories.board_due import DueOrg
from app.services.boards.due_reminders import fire_window

LONDON = {"leave_digest": {"timezone": "Europe/London"}, "boards": {"due_reminder_time": "08:00"}}
# 31 March 2030: London springs forward at 01:00 GMT, so 08:00 local is 07:00 UTC.
SPRING = datetime(2030, 3, 31, 7, 0, tzinfo=UTC)


def _day(config: dict[str, object], now: datetime) -> date | None:
    window = fire_window(DueOrg(org_id=uuid.uuid4(), config=config, policy_timezone=None), now)
    return None if window is None else window.day


def test_the_configured_window_edges_on_a_spring_forward_day() -> None:
    span = timedelta(minutes=settings.boards.due_reminder_window_minutes)
    assert _day(LONDON, SPRING - timedelta(minutes=1)) is None
    assert _day(LONDON, SPRING) == date(2030, 3, 31)
    assert _day(LONDON, SPRING + span - timedelta(minutes=1)) == date(2030, 3, 31)
    assert _day(LONDON, SPRING + span + timedelta(minutes=1)) is None


def test_the_day_bounds_follow_the_zone_across_the_change() -> None:
    window = fire_window(DueOrg(uuid.uuid4(), LONDON, None), SPRING)
    assert window is not None
    # The local day is 23 hours long: midnight GMT to midnight BST.
    assert window.day_start == datetime(2030, 3, 31, 0, 0, tzinfo=UTC)
    assert window.day_end == datetime(2030, 3, 31, 23, 0, tzinfo=UTC)


def test_the_window_is_clipped_at_local_midnight() -> None:
    late = {"leave_digest": {"timezone": "UTC"}, "boards": {"due_reminder_time": "22:30"}}
    assert _day(late, datetime(2030, 3, 4, 23, 59, tzinfo=UTC)) == date(2030, 3, 4)
    assert _day(late, datetime(2030, 3, 5, 0, 30, tzinfo=UTC)) is None


def test_a_default_policy_timezone_is_used_when_the_digest_has_none() -> None:
    config = {"boards": {"due_reminder_time": "08:00"}}
    org = DueOrg(uuid.uuid4(), config, "Asia/Kolkata")
    # 08:30 in Kolkata, 03:00 UTC.
    window = fire_window(org, datetime(2030, 3, 4, 3, 0, tzinfo=UTC))
    assert window is not None and window.day == date(2030, 3, 4)
    assert (
        fire_window(DueOrg(uuid.uuid4(), config, None), datetime(2030, 3, 4, 3, 0, tzinfo=UTC))
        is None
    )
