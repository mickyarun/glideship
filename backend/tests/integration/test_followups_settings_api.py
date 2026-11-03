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

"""The follow-ups settings page's API: off by default, saved per org, zones checked."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.integration.board_api_support import card_team, ok
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration

URL = "/api/v1/me/followups"


async def test_off_by_default_then_saved_and_read_back(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    me = (await card_team(client, pg_session_factory)).editor
    first = ok(await client.get(URL, headers=me.headers))
    assert first["enabled"] is False and first["weekdays_only"] is True
    assert first["send_time"] == "09:00:00"

    body = {
        "enabled": True,
        "send_time": "08:15",
        "timezone": "Asia/Kolkata",
        "weekdays_only": False,
    }
    ok(await client.put(URL, json=body, headers=me.headers))
    saved = ok(await client.get(URL, headers=me.headers))
    assert saved == {**body, "send_time": "08:15:00"}

    prefs = ok(await client.get("/api/v1/me/notification-preferences", headers=me.headers))
    assert "daily_followups" not in {item["key"] for item in prefs["items"]}

    ok(await client.put(URL, json={**body, "enabled": False}, headers=me.headers))
    assert ok(await client.get(URL, headers=me.headers))["enabled"] is False


async def test_an_unknown_timezone_is_refused(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    me = (await card_team(client, pg_session_factory)).editor
    body = {"enabled": True, "send_time": "08:00", "timezone": "Mars/Olympus"}
    response = await client.put(URL, json=body, headers=me.headers)
    assert response.status_code == 422
    assert ok(await client.get(URL, headers=me.headers))["enabled"] is False
