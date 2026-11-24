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

"""A change the manager suggests to a goal, and a goal value cleared on a check-in."""

from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

from app.services.file_storage import FileStorage
from tests.integration.appraisal_month import Month, october
from tests.integration.hr_support import configure_hr_storage
from tests.integration.leave_support import Factory, as_user

pytestmark = pytest.mark.integration
BASE = "/api/v1/appraisals"


@pytest.fixture
def hr_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FileStorage:
    """The shared test HR key (see ``hr_support``)."""
    return configure_hr_storage(monkeypatch, tmp_path)


async def _confirmed(client: AsyncClient, m: Month) -> tuple[str, dict[str, Any]]:
    """Priya's appraisal id and a goal Ravi confirmed for her."""
    mgr = as_user(m.people["mgr"], m.org)
    (row,) = [
        r
        for r in (await client.get(f"{BASE}/team", headers=mgr)).json()
        if r["person_name"] == "Priya"
    ]
    body = {"title": "Fewer reopened bugs", "measure": "Under 8%", "reason": "Q4 focus"}
    page = (await client.post(f"{BASE}/{row['id']}/goals", json=body, headers=mgr)).json()
    return str(row["id"]), page["goals"][0]


async def _own_todo(client: AsyncClient, m: Month) -> list[dict[str, Any]]:
    items = (await client.get(f"{BASE}/todo", headers=as_user(m.people["emp"], m.org))).json()
    return [i for i in items if i["kind"] == "confirm_change"]


async def test_the_person_takes_a_change_their_manager_suggested(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    emp, mgr = as_user(m.people["emp"], m.org), as_user(m.people["mgr"], m.org)
    appraisal, goal = await _confirmed(client, m)
    change = {"title": "Fewer reopened bugs", "measure": "Under 5%", "reason": "New target"}
    sent = await client.post(f"{BASE}/goals/{goal['id']}/suggest-change", json=change, headers=mgr)
    assert sent.status_code == 200, sent.text
    # The manager can't confirm their own change, and doesn't see it as one to confirm.
    (proposal,) = [g for g in sent.json()["goals"] if g["status"] == "proposed"]
    assert proposal["from_manager"] and not proposal["actions"]["accept"]
    manager_todo = (await client.get(f"{BASE}/todo", headers=mgr)).json()
    assert not [i for i in manager_todo if i["kind"] == "confirm_goals"]
    (item,) = await _own_todo(client, m)
    assert (item["target"], item["target_id"], item["count"]) == ("goals", appraisal, 1)
    assert item["due_on"] == "2026-10-08"
    taken = await client.post(f"{BASE}/goals/{proposal['id']}/accept", headers=emp)
    assert taken.status_code == 200, taken.text
    goals = {g["measure"]: g["status"] for g in taken.json()["goals"]}
    assert goals == {"Under 8%": "dismissed", "Under 5%": "accepted"}
    assert await _own_todo(client, m) == []


async def test_the_person_can_decline_it_and_the_manager_take_it_back(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    emp, mgr = as_user(m.people["emp"], m.org), as_user(m.people["mgr"], m.org)
    _, goal = await _confirmed(client, m)
    url = f"{BASE}/goals/{goal['id']}/suggest-change"
    for who in (emp, mgr):
        page = (await client.post(url, json={"title": "Fewer bugs"}, headers=mgr)).json()
        (proposal,) = [g for g in page["goals"] if g["status"] == "proposed"]
        # No reason needed either way: declining it, or taking it back.
        gone = await client.post(
            f"{BASE}/goals/{proposal['id']}/dismiss", json={"reason": ""}, headers=who
        )
        assert gone.status_code == 200, gone.text
    assert await _own_todo(client, m) == []


async def test_clearing_a_goal_value_removes_it(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    emp = as_user(m.people["emp"], m.org)
    _, goal = await _confirmed(client, m)
    (check_in,) = (await client.get("/api/v1/check-ins/mine", headers=emp)).json()
    url = f"/api/v1/check-ins/{check_in['id']}/goal-values/{goal['id']}"
    saved = await client.put(url, json={"value": "7%"}, headers=emp)
    assert saved.json()["goals"][0]["value"] == "7%"
    cleared = await client.put(url, json={"value": "  "}, headers=emp)
    assert cleared.status_code == 200 and not cleared.json()["goals"][0]["value"]
