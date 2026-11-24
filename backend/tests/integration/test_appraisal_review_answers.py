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

"""The self-review's two open answers, and the manager's words to the person."""

from pathlib import Path

import pytest
from httpx import AsyncClient

from app.services.file_storage import FileStorage
from tests.integration.appraisal_review_support import BASE, started
from tests.integration.hr_support import configure_hr_storage
from tests.integration.leave_support import Factory, as_user

pytestmark = pytest.mark.integration
ANSWERS = {"proud": "Shipped refunds early", "differently": "Start write-ups sooner"}


@pytest.fixture
def hr_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FileStorage:
    """The shared test HR key (see ``hr_support``)."""
    return configure_hr_storage(monkeypatch, tmp_path)


async def test_the_open_answers_reach_the_manager_only_once_sent(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m, ids, _ = await started(client, pg_session_factory)
    emp, mgr = as_user(m.people["emp"], m.org), as_user(m.people["mgr"], m.org)
    url = f"{BASE}/{ids['Priya']}"
    goals = [
        {"goal_id": g["id"], "result": "achieved"}
        for g in (await client.get(url, headers=emp)).json()["goals"]
    ]
    saved = await client.put(
        f"{url}/self", json={"band": 3, "goals": goals, **ANSWERS}, headers=emp
    )
    assert saved.json()["self_score"]["proud"] == "Shipped refunds early"
    assert (await client.get(url, headers=mgr)).json()["self_score"] is None
    assert (await client.post(f"{url}/self/submit", headers=emp)).status_code == 200
    theirs = (await client.get(url, headers=mgr)).json()["self_score"]
    assert (theirs["proud"], theirs["differently"]) == tuple(ANSWERS.values())


async def test_the_answers_are_optional(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m, ids, _ = await started(client, pg_session_factory)
    emp = as_user(m.people["emp"], m.org)
    url = f"{BASE}/{ids['Priya']}"
    goals = [
        {"goal_id": g["id"], "result": "partly"}
        for g in (await client.get(url, headers=emp)).json()["goals"]
    ]
    await client.put(f"{url}/self", json={"band": 3, "goals": goals}, headers=emp)
    assert (await client.post(f"{url}/self/submit", headers=emp)).status_code == 200
    assert (await client.get(url, headers=emp)).json()["self_score"]["proud"] == ""
