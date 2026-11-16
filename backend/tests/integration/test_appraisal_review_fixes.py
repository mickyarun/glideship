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

"""The milestone 5 review findings: drafts stay private, results wait for sharing,
approved trends stay in use, and suggestions go through the manager."""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.appraisal import Appraisal
from app.models.appraisal_enums import AppraisalStatus
from app.models.appraisal_goal import AppraisalGoal
from app.services.appraisals import draft_sweeper
from app.services.claude_runner import ClaudeRunResult
from app.services.file_storage import FileStorage
from tests.integration.appraisal_model import Model, model
from tests.integration.appraisal_month import october, run_tick
from tests.integration.appraisal_review_support import BASE, started, team_ids
from tests.integration.hr_support import configure_hr_storage
from tests.integration.leave_support import Factory, as_user

pytestmark = pytest.mark.integration
__all__ = ["model"]  # the fixture, imported for pytest to find


@pytest.fixture
def hr_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FileStorage:
    """The shared test HR key (see ``hr_support``)."""
    return configure_hr_storage(monkeypatch, tmp_path)


async def test_an_unsubmitted_self_score_is_nobodys_to_agree_with(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m, ids, cycle = await started(client, pg_session_factory)
    emp, mgr = as_user(m.people["emp"], m.org), as_user(m.people["mgr"], m.org)
    url = f"{BASE}/{ids['Priya']}"
    review = (await client.get(url, headers=emp)).json()
    goals = [{"goal_id": g["id"], "result": "achieved"} for g in review["goals"]]
    await client.put(f"{url}/self", json={"band": 3, "goals": goals}, headers=emp)
    await run_tick(pg_session_factory, m.org, datetime(2027, 1, 8, 6, tzinfo=UTC))
    seen = (await client.get(url, headers=mgr)).json()
    assert seen["status"] == "manager_review" and seen["self_score"] is None
    agree_all = {"agree": True, "goals": [{"goal_id": g["goal_id"], "agree": True} for g in goals]}
    saved = await client.put(f"{url}/manager", json=agree_all, headers=mgr)
    assert saved.json()["manager_score"]["band"] is None
    assert all(g["draft_result"] is None for g in saved.json()["goals"])
    assert (
        await client.post(f"{url}/manager/submit", json=agree_all, headers=mgr)
    ).status_code == 422
    own = {
        "band": 3,
        "reason": "Steady",
        "goals": [{"goal_id": g["goal_id"], "result": "partly", "reason": "Half"} for g in goals],
    }
    assert (await client.post(f"{url}/manager/submit", json=own, headers=mgr)).status_code == 200
    hr = as_user(m.people["hr"], m.org)
    (team,) = (await client.get(f"{BASE}/cycles/{cycle}/calibration", headers=hr)).json()["teams"]
    assert team["agreement"] is None and team["flag"] is None


async def test_results_reach_the_employee_only_once_shared(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m, ids, _ = await started(client, pg_session_factory)
    emp, mgr = as_user(m.people["emp"], m.org), as_user(m.people["mgr"], m.org)
    hr = as_user(m.people["hr"], m.org)
    url = f"{BASE}/{ids['Priya']}"
    goals = [g["id"] for g in (await client.get(url, headers=emp)).json()["goals"]]
    body = {"band": 3, "goals": [{"goal_id": g, "result": "achieved"} for g in goals]}
    await client.put(f"{url}/self", json=body, headers=emp)
    await client.post(f"{url}/self/submit", headers=emp)
    changed = [
        {"goal_id": g, "agree": False, "result": "not_yet", "reason": "Slipped"} for g in goals
    ]
    await client.put(f"{url}/manager", json={"agree": True, "goals": changed}, headers=mgr)
    async with pg_session_factory() as db:
        rows = (await db.scalars(select(AppraisalGoal).where(AppraisalGoal.org_id == m.org))).all()
    assert {g.final_result for g in rows} == {None}
    await client.post(f"{url}/manager/submit", json={"agree": True, "goals": changed}, headers=mgr)
    # Next quarter's goals open while Q4 waits for HR: no result shows yet.
    nxt = await client.post(f"{BASE}/cycles", json={"period_start": "2027-01-01"}, headers=hr)
    assert (
        await client.post(f"{BASE}/cycles/{nxt.json()['id']}/activate", headers=hr)
    ).status_code == 200
    mine = (await client.get(f"{BASE}/mine", headers=emp)).json()
    new = next(r["id"] for r in mine if r["cycle_name"] == "Q1 2027")
    options = (await client.get(f"{BASE}/{new}/goal-options", headers=emp)).json()
    last = [o for o in options if o["source"] == "last_period"]
    assert last and all(o["last_result"] is None for o in last)
    back = await client.post(f"{url}/send-back", json={"note": "   "}, headers=hr)
    assert back.status_code == 422
    await client.post(f"{url}/share", headers=hr)
    options = (await client.get(f"{BASE}/{new}/goal-options", headers=emp)).json()
    assert {o["last_result"] for o in options if o["source"] == "last_period"} == {"not_yet"}
    await client.post(f"{url}/acknowledge", json={"reply": ""}, headers=emp)
    again = await client.post(f"{url}/acknowledge", json={"reply": "x"}, headers=emp)
    assert again.status_code == 409


async def test_a_trends_draft_waits_while_the_approved_list_stays_in_use(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    hr = as_user(m.people["hr"], m.org)
    template = (await client.get(f"{BASE}/role-templates", headers=hr)).json()[0]
    url = f"{BASE}/role-templates/{template['id']}/trends"
    one = [
        {
            "id": "t1",
            "text": "Chat support grows",
            "source_url": "https://a.test/1",
            "as_of": "2026-10",
        }
    ]
    await client.put(url, json=one, headers=hr)
    v1 = (await client.post(f"{url}/approve", headers=hr)).json()
    assert [t["text"] for t in v1["trends"]] == ["Chat support grows"]
    assert (await client.post(f"{url}/approve", headers=hr)).status_code == 409
    two = [{**one[0], "text": "Agents use AI drafts"}]
    drafted = (await client.put(url, json=two, headers=hr)).json()
    assert [t["text"] for t in drafted["trends"]] == ["Chat support grows"]
    assert [t["text"] for t in drafted["trends_draft"]] == ["Agents use AI drafts"]
    plain = [{**one[0], "source_url": "http://a.test/1"}]
    assert (await client.put(url, json=plain, headers=hr)).status_code == 422
    assert (await client.put(url, json=one * 7, headers=hr)).status_code == 422
    v2 = (await client.post(f"{url}/approve", headers=hr)).json()
    assert v2["trends_version"] == v1["trends_version"] + 1 and v2["trends_draft"] == []
    settings = (await client.get(f"{BASE}/settings", headers=hr)).json()
    await client.put(f"{BASE}/settings", json={**settings, "ai_enabled": False}, headers=hr)
    assert (await client.post(f"{url}/draft", headers=hr)).status_code == 409


async def test_suggestions_and_library_goals_go_through_the_right_person(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage, model: Model
) -> None:
    m = await october(client, pg_session_factory, ai=True)
    emp, mgr = as_user(m.people["emp"], m.org), as_user(m.people["mgr"], m.org)
    appraisal = (await team_ids(client, m))["Priya"]
    await client.post(f"{BASE}/{appraisal}/suggest-goals", headers=emp)
    suggestion = {
        "title": "Attend standup",
        "measure": "yes or no",
        "basis": "role_library",
        "why": "From the library",
        "cites": ["lib:0"],
    }
    model.reply = lambda _p: ClaudeRunResult(
        success=True, output=json.dumps({"goals": [suggestion]})
    )
    await draft_sweeper.tick_once()
    goals = (await client.get(f"{BASE}/{appraisal}/goals", headers=emp)).json()["goals"]
    (picked,) = [g for g in goals if g["status"] == "suggested"]
    edited = await client.patch(
        f"{BASE}/goals/{picked['id']}",
        json={"title": "Run the standup", "measure": "weekly"},
        headers=emp,
    )
    assert edited.status_code == 200
    taken = (await client.post(f"{BASE}/goals/{picked['id']}/accept", headers=emp)).json()
    now = next(g for g in taken["goals"] if g["id"] == picked["id"])
    assert (
        now["status"] == "proposed" and now["why"] == "From the library" and taken["accepted"] == 0
    )
    confirmed = (await client.post(f"{BASE}/goals/{picked['id']}/accept", headers=mgr)).json()
    assert confirmed["accepted"] == 1
    no_reason = await client.patch(
        f"{BASE}/goals/{picked['id']}", json={"title": "Run it daily"}, headers=mgr
    )
    assert no_reason.status_code == 422
    library = await client.post(
        f"{BASE}/{appraisal}/goals",
        json={"title": "From the library", "reason": "Fits Q4", "source": "role_library"},
        headers=mgr,
    )
    lib = next(g for g in library.json()["goals"] if g["title"] == "From the library")
    assert lib["origin"] == "manager_added" and lib["actions"]["remove"] is True
    assert (await client.delete(f"{BASE}/goals/{lib['id']}", headers=mgr)).json()["accepted"] == 1


async def test_a_suggestion_run_that_ends_after_the_lock_saves_nothing(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage, model: Model
) -> None:
    m = await october(client, pg_session_factory, ai=True)
    emp = as_user(m.people["emp"], m.org)
    appraisal = (await team_ids(client, m))["Priya"]
    await client.post(f"{BASE}/{appraisal}/suggest-goals", headers=emp)

    async def late(_prompt: str) -> ClaudeRunResult:
        async with pg_session_factory() as db:
            row = await db.get(Appraisal, uuid.UUID(appraisal))
            assert row is not None
            row.status = AppraisalStatus.SELF_REVIEW
            await db.commit()
        goal = {
            "title": "X",
            "measure": "y",
            "basis": "role_library",
            "why": "z",
            "cites": ["lib:0"],
        }
        return ClaudeRunResult(success=True, output=json.dumps({"goals": [goal]}))

    model.reply = late
    await draft_sweeper.tick_once()
    async with pg_session_factory() as db:
        goals = (
            await db.scalars(select(AppraisalGoal).where(AppraisalGoal.org_id == m.org))
        ).all()
        row = await db.get(Appraisal, uuid.UUID(appraisal))
    assert goals == [] and row is not None and row.suggest_status.value == "none"
