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

"""The goal limit comes from the org's settings and applies to a running cycle."""

from pathlib import Path

import pytest
from httpx import AsyncClient

from app.services.file_storage import FileStorage
from tests.integration.appraisal_month import october
from tests.integration.hr_support import configure_hr_storage
from tests.integration.leave_support import Factory, as_user

pytestmark = pytest.mark.integration
BASE = "/api/v1/appraisals"


@pytest.fixture
def hr_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FileStorage:
    """The shared test HR key (see ``hr_support``)."""
    return configure_hr_storage(monkeypatch, tmp_path)


async def test_the_limit_follows_the_org_setting_mid_cycle(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    mgr, hr = as_user(m.people["mgr"], m.org), as_user(m.people["hr"], m.org)
    (mine,) = (await client.get(f"{BASE}/mine", headers=as_user(m.people["emp"], m.org))).json()
    url = f"{BASE}/{mine['id']}/goals"

    async def add(title: str) -> int:
        body = {"title": title, "reason": "Q4 focus"}
        return (await client.post(url, json=body, headers=mgr)).status_code

    async def set_limit(n: int) -> int:
        settings = (await client.get(f"{BASE}/settings", headers=hr)).json()
        put = await client.put(f"{BASE}/settings", json={**settings, "max_goals": n}, headers=hr)
        return put.status_code

    assert [await add(f"Goal {n}") for n in range(4)] == [201, 201, 201, 409]
    assert (await client.get(url, headers=mgr)).json()["limit"] == 3

    # Raised mid-cycle: the running cycle gets the extra slots at once.
    assert await set_limit(5) == 200
    assert [await add(f"More {n}") for n in range(3)] == [201, 201, 409]
    body = (await client.get(url, headers=mgr)).json()
    assert (body["limit"], body["accepted"]) == (5, 5)

    # Lowered: confirmed goals stay; only new ones stop, even into a freed low slot.
    second = next(g for g in body["goals"] if g["position"] == 2)
    assert (await client.delete(f"{BASE}/goals/{second['id']}", headers=mgr)).status_code == 200
    assert await set_limit(2) == 200
    body = (await client.get(url, headers=mgr)).json()
    assert (body["limit"], body["accepted"]) == (2, 4)
    assert await add("Too many") == 409
    own = {"title": "My own idea"}
    proposed = await client.post(url, json=own, headers=as_user(m.people["emp"], m.org))
    assert proposed.status_code == 201
    idea = next(g for g in proposed.json()["goals"] if g["title"] == "My own idea")
    accepted = await client.post(f"{BASE}/goals/{idea['id']}/accept", headers=mgr)
    assert accepted.status_code == 409

    assert await set_limit(0) == 422
    assert await set_limit(21) == 422
