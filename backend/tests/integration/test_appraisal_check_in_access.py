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

"""Who may change what on a check-in, goal values on real goals, and link removal."""

import uuid
from datetime import date
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import GoalOrigin, GoalStatus
from app.models.appraisal_goal import AppraisalGoal
from app.repositories.employee_profile import EmployeeProfileRepository
from app.services.appraisals import crypto
from app.services.file_storage import FileStorage
from tests.integration.appraisal_month import Month, october
from tests.integration.hr_support import configure_hr_storage
from tests.integration.leave_support import Factory, as_user, setup_org

pytestmark = pytest.mark.integration
CHECK_INS = "/api/v1/check-ins"


@pytest.fixture
def hr_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FileStorage:
    """The shared test HR key (see ``hr_support``)."""
    return configure_hr_storage(monkeypatch, tmp_path)


async def _mine(client: AsyncClient, m: Month) -> str:
    rows = (await client.get(f"{CHECK_INS}/mine", headers=as_user(m.people["emp"], m.org))).json()
    return str(rows[0]["id"])


async def _goal(factory: Factory, m: Month) -> uuid.UUID:
    async with factory() as db:
        profile = await EmployeeProfileRepository(db, org_id=m.org).get_by_user(m.people["emp"])
        cycle = await db.scalar(select(AppraisalCycle).where(AppraisalCycle.org_id == m.org))
        assert profile is not None and cycle is not None
        goal = AppraisalGoal(
            org_id=m.org,
            profile_id=profile.id,
            cycle_id=cycle.id,
            target_period_start=date(2026, 10, 1),
            position=1,
            origin=GoalOrigin.MANAGER_ADDED,
            status=GoalStatus.ACCEPTED,
        )
        crypto.seal(goal, "title", "Close in 5 days")
        db.add(goal)
        await db.commit()
        return goal.id


async def test_a_manager_can_change_nothing_on_a_reports_check_in(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    url = f"{CHECK_INS}/{await _mine(client, m)}"
    manager = as_user(m.people["mgr"], m.org)
    tag = {str(m.counted): {"heading": "team"}}
    link = {"url": "https://example.com", "title": "x", "heading": "team"}
    for method, path, body in (
        ("put", "/fact-tags", tag),
        ("post", "/links", link),
        ("put", f"/goal-values/{uuid.uuid4()}", {"value": "1"}),
    ):
        response = await client.request(method, f"{url}{path}", json=body, headers=manager)
        assert response.status_code == 404, path


async def test_hr_reads_and_another_org_gets_nothing(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    url = f"{CHECK_INS}/{await _mine(client, m)}"
    assert (await client.get(url, headers=as_user(m.people["hr"], m.org))).status_code == 200
    other_org, (outsider,), _ = await setup_org(pg_session_factory, "Outsider")
    assert (await client.get(url, headers=as_user(outsider, other_org))).status_code == 404


async def test_goal_values_only_for_the_periods_goals(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    goal = await _goal(pg_session_factory, m)
    url = f"{CHECK_INS}/{await _mine(client, m)}"
    me = as_user(m.people["emp"], m.org)
    body = {"value": "6 days", "source_note": "Close checklist"}
    saved = await client.put(f"{url}/goal-values/{goal}", json=body, headers=me)
    assert saved.status_code == 200, saved.text
    panel = saved.json()["goals"][0]
    assert (panel["value"], panel["source_note"]) == ("6 days", "Close checklist")
    assert saved.json()["status"] == "employee_added"
    stray = {str(m.counted): {"goal_id": str(uuid.uuid4())}}
    assert (await client.put(f"{url}/fact-tags", json=stray, headers=me)).status_code == 422


async def test_removing_a_link_removes_its_tag(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    url = f"{CHECK_INS}/{await _mine(client, m)}"
    me = as_user(m.people["emp"], m.org)
    link = {"url": "https://example.com/doc", "title": "Doc", "heading": "initiative"}
    link_id = (await client.post(f"{url}/links", json=link, headers=me)).json()["links"][0]["id"]
    await client.put(f"{url}/fact-tags", json={link_id: {"heading": "growth"}}, headers=me)
    assert (await client.delete(f"{url}/links/{link_id}", headers=me)).status_code == 204
    after = (await client.get(url, headers=me)).json()
    assert after["links"] == [] and link_id not in after["fact_tags"]
    gone = await client.delete(f"{url}/links/{link_id}", headers=me)
    assert gone.status_code == 404


async def test_only_hr_creates_or_opens_cycles(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    manager = as_user(m.people["mgr"], m.org)
    created = await client.post(
        "/api/v1/appraisals/cycles", json={"period_start": "2027-01-01"}, headers=manager
    )
    assert created.status_code == 403
