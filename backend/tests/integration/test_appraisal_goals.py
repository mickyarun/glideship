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

"""Goals: proposing, confirming, rewording, declining, editing, the limit and the lock."""

import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.models.appraisal import Appraisal
from app.models.appraisal_enums import AppraisalStatus
from app.models.employee_audit_event import EmployeeAuditAction, EmployeeAuditEvent
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


async def _priya(client: AsyncClient, m: Month) -> str:
    mine = (await client.get(f"{BASE}/mine", headers=as_user(m.people["emp"], m.org))).json()
    assert len(mine) == 1
    return str(mine[0]["id"])


def _goal(body: dict, title: str) -> dict:
    return next(g for g in body["goals"] if g["title"] == title)


async def test_an_own_goal_waits_for_the_manager_and_is_audited_when_confirmed(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    emp, mgr = as_user(m.people["emp"], m.org), as_user(m.people["mgr"], m.org)
    appraisal = await _priya(client, m)
    created = await client.post(
        f"{BASE}/{appraisal}/goals",
        json={"title": "UAT automation at 80%", "measure": "test report"},
        headers=emp,
    )
    assert created.status_code == 201, created.text
    goal = _goal(created.json(), "UAT automation at 80%")
    assert goal["status"] == "proposed" and goal["origin"] == "employee_own"
    assert goal["actions"]["accept"] is False and goal["actions"]["dismiss"] is True
    seen = (await client.get(f"{BASE}/{appraisal}/goals", headers=mgr)).json()
    assert _goal(seen, "UAT automation at 80%")["actions"]["accept"] is True
    reword = await client.post(
        f"{BASE}/goals/{goal['id']}/ask-reword", json={"reason": "Say which suite"}, headers=mgr
    )
    assert _goal(reword.json(), "UAT automation at 80%")["reword_note"] == "Say which suite"
    edited = await client.patch(
        f"{BASE}/goals/{goal['id']}",
        json={"title": "Refunds UAT automation at 80%", "measure": "test report"},
        headers=emp,
    )
    assert edited.status_code == 200
    confirmed = await client.post(f"{BASE}/goals/{goal['id']}/accept", headers=mgr)
    row = _goal(confirmed.json(), "Refunds UAT automation at 80%")
    assert row["status"] == "accepted" and row["position"] == 1
    assert [h["kind"] for h in row["history"]] == [
        "created",
        "reword_asked",
        "edited",
        "confirmed",
    ]
    async with pg_session_factory() as db:
        targets = (
            await db.scalars(
                select(EmployeeAuditEvent.target).where(
                    EmployeeAuditEvent.org_id == m.org,
                    EmployeeAuditEvent.action == EmployeeAuditAction.APPRAISAL_GOAL_ACCEPTED,
                )
            )
        ).all()
    assert targets == [goal["id"]]


async def test_declining_needs_a_reason_the_employee_sees(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    emp, mgr = as_user(m.people["emp"], m.org), as_user(m.people["mgr"], m.org)
    appraisal = await _priya(client, m)
    body = (
        await client.post(f"{BASE}/{appraisal}/goals", json={"title": "Learn Go"}, headers=emp)
    ).json()
    goal_id = _goal(body, "Learn Go")["id"]
    assert (
        await client.post(f"{BASE}/goals/{goal_id}/dismiss", json={}, headers=mgr)
    ).status_code == 422
    await client.post(
        f"{BASE}/goals/{goal_id}/dismiss", json={"reason": "Not this period"}, headers=mgr
    )
    mine = (await client.get(f"{BASE}/{appraisal}/goals", headers=emp)).json()
    declined = _goal(mine, "Learn Go")
    assert declined["status"] == "dismissed" and declined["dismiss_reason"] == "Not this period"
    assert mine["accepted"] == 0


async def test_three_confirmed_goals_at_most_and_managers_say_why(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    mgr = as_user(m.people["mgr"], m.org)
    appraisal = await _priya(client, m)
    url = f"{BASE}/{appraisal}/goals"
    assert (await client.post(url, json={"title": "No reason"}, headers=mgr)).status_code == 422
    for n in range(3):
        added = await client.post(
            url, json={"title": f"Goal {n}", "reason": "Q4 focus"}, headers=mgr
        )
        assert added.status_code == 201
    full = await client.post(url, json={"title": "Fourth", "reason": "x"}, headers=mgr)
    assert full.status_code == 409
    body = (await client.get(url, headers=mgr)).json()
    assert body["accepted"] == 3
    first = _goal(body, "Goal 0")
    assert first["origin"] == "manager_added" and first["actions"]["remove"] is True
    no_reason = await client.patch(
        f"{BASE}/goals/{first['id']}", json={"title": "Goal zero"}, headers=mgr
    )
    assert no_reason.status_code == 422
    changed = await client.patch(
        f"{BASE}/goals/{first['id']}",
        json={"title": "Goal zero", "reason": "Clearer"},
        headers=mgr,
    )
    history = _goal(changed.json(), "Goal zero")["history"]
    assert history[-1]["before"]["title"] == "Goal 0" and history[-1]["reason"] == "Clearer"
    removed = await client.delete(f"{BASE}/goals/{first['id']}", headers=mgr)
    assert removed.json()["accepted"] == 2


async def test_a_suggested_change_replaces_the_goal_once_confirmed(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    emp, mgr = as_user(m.people["emp"], m.org), as_user(m.people["mgr"], m.org)
    appraisal = await _priya(client, m)
    body = (
        await client.post(
            f"{BASE}/{appraisal}/goals", json={"title": "Old", "reason": "x"}, headers=mgr
        )
    ).json()
    old = _goal(body, "Old")
    assert old["actions"]["edit"] is True
    mine = (await client.get(f"{BASE}/{appraisal}/goals", headers=emp)).json()
    assert _goal(mine, "Old")["actions"]["suggest_change"] is True
    assert _goal(mine, "Old")["actions"]["edit"] is False
    suggested = await client.post(
        f"{BASE}/goals/{old['id']}/suggest-change",
        json={"title": "New", "reason": "Scope moved"},
        headers=emp,
    )
    change = _goal(suggested.json(), "New")
    assert change["replaces"] == old["id"] and change["status"] == "proposed"
    again = await client.post(
        f"{BASE}/goals/{old['id']}/suggest-change", json={"title": "Newer"}, headers=emp
    )
    assert again.status_code == 409
    done = (await client.post(f"{BASE}/goals/{change['id']}/accept", headers=mgr)).json()
    assert _goal(done, "New")["position"] == old["position"]
    assert _goal(done, "Old")["status"] == "dismissed" and done["accepted"] == 1


async def test_goals_lock_when_the_self_review_opens_and_strangers_see_nothing(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    emp = as_user(m.people["emp"], m.org)
    appraisal = await _priya(client, m)
    stranger = as_user(m.people["stranger"], m.org)
    assert (await client.get(f"{BASE}/{appraisal}/goals", headers=stranger)).status_code == 404
    async with pg_session_factory() as db:
        await db.execute(
            update(Appraisal)
            .where(Appraisal.id == uuid.UUID(appraisal))
            .values(status=AppraisalStatus.SELF_REVIEW)
        )
        await db.commit()
    body = (await client.get(f"{BASE}/{appraisal}/goals", headers=emp)).json()
    assert body["locked"] is True and body["can_propose"] is False
    refused = await client.post(f"{BASE}/{appraisal}/goals", json={"title": "Late"}, headers=emp)
    assert refused.status_code == 409


async def test_goal_options_come_from_the_role_library(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    emp = as_user(m.people["emp"], m.org)
    appraisal = await _priya(client, m)
    options = (await client.get(f"{BASE}/{appraisal}/goal-options", headers=emp)).json()
    assert options and {o["source"] for o in options} == {"role_library"}
    picked = await client.post(
        f"{BASE}/{appraisal}/goals",
        json={
            "title": options[0]["title"],
            "measure": options[0]["measure"],
            "source": "role_library",
        },
        headers=emp,
    )
    goal = _goal(picked.json(), options[0]["title"])
    assert goal["origin"] == "role_library" and goal["status"] == "proposed"
    team = (await client.get(f"{BASE}/team", headers=as_user(m.people["mgr"], m.org))).json()
    assert {r["person_name"]: r["goals_proposed"] for r in team} == {"Priya": 1, "Meena": 0}
