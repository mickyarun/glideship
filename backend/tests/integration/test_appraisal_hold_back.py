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

"""Flagged results wait for HR's "Looks fair"; HR's reminder claims its day once."""

import asyncio
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

from app.services.file_storage import FileStorage
from tests.integration.appraisal_month import Month
from tests.integration.appraisal_review_support import BASE, started
from tests.integration.board_notify_support import fake_slack, link_slack
from tests.integration.hr_support import configure_hr_storage
from tests.integration.leave_support import Factory, as_user

pytestmark = pytest.mark.integration


@pytest.fixture
def hr_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FileStorage:
    """The shared test HR key (see ``hr_support``)."""
    return configure_hr_storage(monkeypatch, tmp_path)


async def _to_hr(client: AsyncClient, m: Month, ids: dict[str, str]) -> str:
    """Priya's self-review and Ravi's review, with a concern flagged; her review's URL."""
    emp, mgr = as_user(m.people["emp"], m.org), as_user(m.people["mgr"], m.org)
    url = f"{BASE}/{ids['Priya']}"
    goals = [g["id"] for g in (await client.get(url, headers=emp)).json()["goals"]]
    own = {
        "band": 3,
        "reason": "Steady",
        "goals": [{"goal_id": g, "result": "achieved"} for g in goals],
    }
    assert (await client.put(f"{url}/self", json=own, headers=emp)).status_code == 200
    assert (await client.post(f"{url}/self/submit", headers=emp)).status_code == 200
    review = {
        "agree": True,
        "band": 3,
        "reason": "Steady quarter",
        "goals": [{"goal_id": g, "agree": True} for g in goals],
        "ready_next_level": False,
        "performance_concern": True,
        "concern_note": "Watch delivery",
    }
    sent = await client.post(f"{url}/manager/submit", json=review, headers=mgr)
    assert sent.status_code == 200, sent.text
    return url


async def _priya(client: AsyncClient, cycle: str, hr: dict[str, str]) -> dict[str, Any]:
    calibration = (await client.get(f"{BASE}/cycles/{cycle}/calibration", headers=hr)).json()
    (priya,) = [p for p in calibration["people"] if p["name"] == "Priya"]
    return dict(priya)


async def test_a_flagged_result_waits_until_hr_finds_it_fair(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m, ids, cycle = await started(client, pg_session_factory)
    mgr, hr = as_user(m.people["mgr"], m.org), as_user(m.people["hr"], m.org)
    await _to_hr(client, m, ids)
    priya = await _priya(client, cycle, hr)
    assert priya["concern"] and priya["held"] and priya["looks_fair_at"] is None
    assert priya["manager_user_id"] == str(m.people["mgr"])
    # Held back: sharing everything ready leaves it out.
    shared = await client.post(f"{BASE}/cycles/{cycle}/share", headers=hr)
    assert shared.json() == {"shared": 0}
    fair_url = f"{BASE}/cycles/{cycle}/looks-fair"
    fair = {"appraisal_ids": [ids["Priya"]]}
    # Only HR marks results fair.
    assert (await client.post(fair_url, json=fair, headers=mgr)).status_code == 403
    assert (await client.post(fair_url, json=fair, headers=hr)).json() == {"marked": 1}
    priya = await _priya(client, cycle, hr)
    assert not priya["held"] and priya["looks_fair_by_name"] == "Hr"
    shared = await client.post(f"{BASE}/cycles/{cycle}/share", headers=hr)
    assert shared.json() == {"shared": 1}


async def test_a_sent_back_review_is_looked_at_again(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m, ids, cycle = await started(client, pg_session_factory)
    mgr, hr = as_user(m.people["mgr"], m.org), as_user(m.people["hr"], m.org)
    url = await _to_hr(client, m, ids)
    fair = {"appraisal_ids": [ids["Priya"]]}
    await client.post(f"{BASE}/cycles/{cycle}/looks-fair", json=fair, headers=hr)
    assert not (await _priya(client, cycle, hr))["held"]
    await client.post(f"{url}/send-back", json={"note": "Say more"}, headers=hr)
    review = (await client.get(url, headers=mgr)).json()["manager_score"]
    assert review is not None
    priya = await _priya(client, cycle, hr)
    assert priya["looks_fair_at"] is None and priya["status"] == "manager_review"


async def test_two_reminder_clicks_at_once_send_once(
    client: AsyncClient,
    pg_session_factory: Factory,
    hr_key: FileStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    m, _, cycle = await started(client, pg_session_factory)
    fake_slack(monkeypatch, pg_session_factory)
    await link_slack(pg_session_factory, m.org, m.people["emp"], m.people["quiet"])
    hr = as_user(m.people["hr"], m.org)
    url = f"{BASE}/cycles/{cycle}/remind"
    first, second = await asyncio.gather(
        client.post(url, headers=hr), client.post(url, headers=hr)
    )
    assert sorted([first.status_code, second.status_code]) == [200, 409]
    progress = (await client.get(f"{BASE}/cycles/{cycle}/progress", headers=hr)).json()
    assert progress["reminded_today"]
