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


from __future__ import annotations

import uuid
from datetime import time

from app.repositories.followup_settings import SubscriberRow
from app.repositories.followup_zone import ZoneParts
from app.services.followups.schedule import Subscriber
from app.services.followups.zone import default_zone

ORG = uuid.uuid4()
DIGEST = {"leave_digest": {"timezone": "America/New_York"}}


def test_their_own_leave_policy_zone_comes_first() -> None:
    parts = ZoneParts(own_policy="Asia/Kolkata", default_policy="Europe/London", org_config=DIGEST)
    assert default_zone(parts, ORG) == "Asia/Kolkata"


def test_otherwise_the_org_zone_the_card_reminder_uses() -> None:
    assert default_zone(ZoneParts(None, "Europe/London", DIGEST), ORG) == "America/New_York"
    assert default_zone(ZoneParts(None, "Europe/London", None), ORG) == "Europe/London"
    assert default_zone(ZoneParts(None, None, None), ORG) == "UTC"


def test_a_saved_zone_beats_the_default() -> None:
    row = SubscriberRow(
        org_id=ORG,
        user_id=uuid.uuid4(),
        send_time=time(9, 0),
        weekdays_only=True,
        saved_zone="Pacific/Auckland",
        zone=ZoneParts("Asia/Kolkata", None, None),
    )
    assert Subscriber.of(row).timezone == "Pacific/Auckland"
    unsaved = SubscriberRow(**{**row.__dict__, "saved_zone": None})
    assert Subscriber.of(unsaved).timezone == "Asia/Kolkata"
