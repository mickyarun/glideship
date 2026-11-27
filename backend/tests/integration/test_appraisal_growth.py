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

"""The growth conversation: open after sharing, no band, next goals join the next cycle."""

from pathlib import Path

import pytest
from httpx import AsyncClient

from app.services.file_storage import FileStorage
from tests.integration.appraisal_review_support import BASE, started
from tests.integration.hr_support import configure_hr_storage
from tests.integration.leave_support import Factory, as_user

pytestmark = pytest.mark.integration


@pytest.fixture
def hr_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FileStorage:
    """The shared test HR key (see ``hr_support``)."""
    return configure_hr_storage(monkeypatch, tmp_path)


async def test_the_growth_conversation_and_next_periods_goals(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m, ids, _ = await started(client, pg_session_factory)
    emp, mgr = as_user(m.people["emp"], m.org), as_user(m.people["mgr"], m.org)
    hr = as_user(m.people["hr"], m.org)
    url = f"{BASE}/{ids['Priya']}"
    talk = {"strength": "Catching regressions early", "focus": "Plan UAT sooner"}
    early = await client.put(f"{url}/growth", json=talk, headers=mgr)
    assert early.status_code == 409
    review = (await client.get(url, headers=emp)).json()
    assert review["growth"]["open"] is False
    goals = [{"goal_id": g["id"], "result": "achieved"} for g in review["goals"]]
    await client.put(f"{url}/self", json={"band": 3, "goals": goals}, headers=emp)
    await client.post(f"{url}/self/submit", headers=emp)
    agree = {
        "agree": True,
        "reason": "A steady quarter",
        "goals": [{"goal_id": g["goal_id"], "agree": True} for g in goals],
    }
    await client.post(f"{url}/manager/submit", json=agree, headers=mgr)
    await client.post(f"{url}/share", headers=hr)

    saved = (await client.put(f"{url}/growth", json=talk, headers=mgr)).json()["growth"]
    assert saved["open"] and saved["strength"] == "Catching regressions early"
    assert saved["next_period_start"] == "2026-11-01"
    added = await client.post(
        f"{url}/next-goals",
        json={"title": "Refunds UAT at 90%", "measure": "test report"},
        headers=mgr,
    )
    assert added.status_code == 201
    proposed = (
        await client.post(f"{url}/next-goals", json={"title": "Learn load testing"}, headers=emp)
    ).json()["growth"]["goals"]
    mine = next(g for g in proposed if g["title"] == "Learn load testing")
    theirs = next(g for g in proposed if g["title"] == "Refunds UAT at 90%")
    assert (mine["status"], theirs["status"]) == ("proposed", "accepted")
    assert mine["can_remove"] and not theirs["can_remove"]
    assert not mine["can_reject"] and not theirs["can_reject"]
    refused = await client.delete(f"{url}/next-goals/{theirs['id']}", headers=emp)
    assert refused.status_code == 409
    # The manager rejects a proposal, saying why if they like; the employee sees it.
    extra = (
        await client.post(f"{url}/next-goals", json={"title": "Write a blog"}, headers=emp)
    ).json()["growth"]["goals"]
    blog = next(g for g in extra if g["title"] == "Write a blog")
    as_mgr = (await client.get(url, headers=mgr)).json()["growth"]["goals"]
    seen = next(g for g in as_mgr if g["id"] == blog["id"])
    assert seen["can_reject"] and not seen["can_remove"]
    reject_url = f"{url}/next-goals/{blog['id']}/reject"
    no = await client.post(reject_url, json={}, headers=emp)
    assert no.status_code == 409
    # Only the primary manager rejects: not HR, not the manager's own manager.
    boss = as_user(m.people["boss"], m.org)
    for other in (hr, boss):
        refused_other = await client.post(reject_url, json={}, headers=other)
        assert refused_other.status_code in (404, 409), refused_other.text
    gone = await client.post(
        f"{url}/next-goals/{blog['id']}/reject", json={"reason": "Next year"}, headers=mgr
    )
    assert gone.status_code == 200, gone.text
    after = (await client.get(url, headers=emp)).json()["growth"]
    assert [(r["title"], r["reason"]) for r in after["rejected"]] == [
        ("Write a blog", "Next year")
    ]
    assert blog["id"] not in {g["id"] for g in after["goals"]}
    # Only the person and their manager see a rejection.
    assert (await client.get(url, headers=hr)).json()["growth"]["rejected"] == []
    boss_view = await client.get(url, headers=boss)
    if boss_view.status_code == 200:
        assert boss_view.json()["growth"]["rejected"] == []
    confirmed = (await client.post(f"{url}/next-goals/{mine['id']}/accept", headers=mgr)).json()
    assert {g["status"] for g in confirmed["growth"]["goals"]} == {"accepted"}
    hr_view = (await client.get(url, headers=hr)).json()["growth"]
    assert hr_view["can_edit"] is False and len(hr_view["goals"]) == 2

    nxt = await client.post(f"{BASE}/cycles", json={"period_start": "2026-11-01"}, headers=hr)
    assert nxt.status_code == 201, nxt.text
    opened = await client.post(f"{BASE}/cycles/{nxt.json()['id']}/activate", headers=hr)
    assert opened.status_code == 200
    rows = (await client.get(f"{BASE}/mine", headers=emp)).json()
    new = next(r for r in rows if r["period_start"] == "2026-11-01")
    assert new["goals_accepted"] == 2
    page = (await client.get(f"{BASE}/{new['id']}/goals", headers=emp)).json()
    assert {g["title"] for g in page["goals"] if g["status"] == "accepted"} == {
        "Refunds UAT at 90%",
        "Learn load testing",
    }
