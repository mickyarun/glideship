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

"""Review forms take as many goals as the org allows, not a fixed three."""

from pathlib import Path

import pytest
from httpx import AsyncClient

from app.services.file_storage import FileStorage
from tests.integration.appraisal_month import october
from tests.integration.appraisal_review_support import (
    BASE,
    cycle_id,
    end_period_early,
    team_ids,
)
from tests.integration.hr_support import configure_hr_storage
from tests.integration.leave_support import Factory, as_user

pytestmark = pytest.mark.integration
GOALS = 5


@pytest.fixture
def hr_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FileStorage:
    """The shared test HR key (see ``hr_support``)."""
    return configure_hr_storage(monkeypatch, tmp_path)


async def test_a_review_with_more_than_three_goals_saves_and_submits(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    emp, mgr = as_user(m.people["emp"], m.org), as_user(m.people["mgr"], m.org)
    hr = as_user(m.people["hr"], m.org)
    settings = (await client.get(f"{BASE}/settings", headers=hr)).json()
    put = await client.put(f"{BASE}/settings", json={**settings, "max_goals": GOALS}, headers=hr)
    assert put.status_code == 200
    ids, cycle = await team_ids(client, m), await cycle_id(client, m)
    for n in range(GOALS):
        body = {"title": f"Goal {n}", "reason": "Q4 focus"}
        added = await client.post(f"{BASE}/{ids['Priya']}/goals", json=body, headers=mgr)
        assert added.status_code == 201
    await end_period_early(pg_session_factory, m.org)
    opened = await client.post(f"{BASE}/cycles/{cycle}/start-review", headers=hr)
    assert opened.status_code == 202

    url = f"{BASE}/{ids['Priya']}"
    review = (await client.get(url, headers=emp)).json()
    goal_ids = [g["id"] for g in review["goals"]]
    assert len(goal_ids) == GOALS
    scored = [{"goal_id": g, "result": "achieved", "reason": "Done"} for g in goal_ids]

    twice = {"band": 3, "goals": [*scored, scored[0]]}
    assert (await client.put(f"{url}/self", json=twice, headers=emp)).status_code == 422
    saved = await client.put(f"{url}/self", json={"band": 3, "goals": scored}, headers=emp)
    assert saved.status_code == 200
    assert {g["self_result"] for g in saved.json()["goals"]} == {"achieved"}
    assert (await client.post(f"{url}/self/submit", headers=emp)).status_code == 200

    agree = {"agree": True, "goals": [{"goal_id": g, "agree": True} for g in goal_ids]}
    sent = await client.post(f"{url}/manager/submit", json=agree, headers=mgr)
    assert sent.status_code == 200
    assert sent.json()["status"] == "calibration"
