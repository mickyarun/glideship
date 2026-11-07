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

"""Manager feedback: items opening on the tick, who reads and writes them, done rules."""

import uuid
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.appraisal_enums import FeedbackStatus, GoalOrigin, GoalStatus
from app.models.appraisal_goal import AppraisalGoal
from app.models.appraisal_manager_feedback import AppraisalManagerFeedback
from app.models.employee_audit_event import EmployeeAuditAction, EmployeeAuditEvent
from app.repositories.employee_profile import EmployeeProfileRepository
from app.services.appraisals import crypto
from app.services.file_storage import FileStorage
from tests.integration.appraisal_month import NOV_2, Month, october, run_tick
from tests.integration.hr_support import configure_hr_storage
from tests.integration.leave_support import Factory, as_user, give_role, report_to, setup_org

pytestmark = pytest.mark.integration
FEEDBACK = "/api/v1/manager-feedback"
CHECK_INS = "/api/v1/check-ins"


@pytest.fixture
def hr_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FileStorage:
    """The shared test HR key (see ``hr_support``)."""
    return configure_hr_storage(monkeypatch, tmp_path)


async def _profile(factory: Factory, org: uuid.UUID, user: uuid.UUID) -> uuid.UUID:
    async with factory() as db:
        profile = await EmployeeProfileRepository(db, org_id=org).get_by_user(user)
        assert profile is not None
        return profile.id


async def _items(factory: Factory, org: uuid.UUID) -> list[AppraisalManagerFeedback]:
    async with factory() as db:
        return list(
            await db.scalars(
                select(AppraisalManagerFeedback)
                .where(AppraisalManagerFeedback.org_id == org)
                .order_by(AppraisalManagerFeedback.period_start)
            )
        )


async def _emp_item(factory: Factory, m: Month) -> AppraisalManagerFeedback:
    profile_id = await _profile(factory, m.org, m.people["emp"])
    return next(i for i in await _items(factory, m.org) if i.profile_id == profile_id)


async def test_the_tick_opens_one_item_per_report_once(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    items = await _items(pg_session_factory, m.org)
    assert len(items) == 2
    assert {i.manager_user_id for i in items} == {m.people["mgr"]}
    assert {(i.period_start, i.period_end, i.due_on) for i in items} == {
        (date(2026, 10, 1), date(2026, 10, 31), date(2026, 11, 10))
    }
    await run_tick(pg_session_factory, m.org, datetime(2026, 11, 3, 6, tzinfo=UTC))
    assert len(await _items(pg_session_factory, m.org)) == 2


async def test_the_employee_sees_feedback_once_the_manager_saves_it(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    item = await _emp_item(pg_session_factory, m)
    emp, mgr = as_user(m.people["emp"], m.org), as_user(m.people["mgr"], m.org)
    assert (await client.get(f"{FEEDBACK}/{item.id}", headers=emp)).status_code == 404
    saved = await client.put(
        f"{FEEDBACK}/{item.id}",
        json={"keep": "Catching regressions early", "try_next": ""},
        headers=mgr,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["status"] == "open" and saved.json()["can_edit"]
    seen = await client.get(f"{FEEDBACK}/{item.id}", headers=emp)
    assert seen.status_code == 200
    assert seen.json()["keep"] == "Catching regressions early"
    assert not seen.json()["can_edit"]
    mine = (await client.get(f"{CHECK_INS}/mine", headers=emp)).json()
    october_check_in = next(c for c in mine if c["period_start"] == "2026-10-01")
    page = (await client.get(f"{CHECK_INS}/{october_check_in['id']}", headers=emp)).json()
    assert page["feedback"]["keep"] == "Catching regressions early"
    assert page["feedback"]["done"] is False
    async with pg_session_factory() as db:
        row = await db.get(AppraisalManagerFeedback, item.id)
        assert row is not None and row.keep_note is not None
        assert b"regressions" not in row.keep_note


async def test_done_needs_both_lines_and_is_audited(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    item = await _emp_item(pg_session_factory, m)
    mgr = as_user(m.people["mgr"], m.org)
    url = f"{FEEDBACK}/{item.id}"
    await client.put(url, json={"keep": "Clear PRs"}, headers=mgr)
    assert (await client.post(f"{url}/done", headers=mgr)).status_code == 422
    await client.put(url, json={"keep": "Clear PRs", "try_next": "Pair on UAT"}, headers=mgr)
    done = await client.post(f"{url}/done", headers=mgr)
    assert done.status_code == 200 and done.json()["status"] == "done"
    assert done.json()["done_at"] is not None
    async with pg_session_factory() as db:
        events = list(
            await db.scalars(
                select(EmployeeAuditEvent).where(
                    EmployeeAuditEvent.org_id == m.org,
                    EmployeeAuditEvent.action == EmployeeAuditAction.APPRAISAL_FEEDBACK_GIVEN,
                )
            )
        )
    assert [e.target for e in events] == [str(item.id)]
    # Clearing a line takes it back to open: done always means both lines.
    reopened = await client.put(url, json={"keep": "Clear PRs", "try_next": ""}, headers=mgr)
    assert reopened.json()["status"] == "open"


async def test_only_the_primary_manager_writes(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    item = await _emp_item(pg_session_factory, m)
    url = f"{FEEDBACK}/{item.id}"
    await client.put(
        url, json={"keep": "a", "try_next": "b"}, headers=as_user(m.people["mgr"], m.org)
    )
    body = {"keep": "rewritten", "try_next": "by someone else"}
    for who in ("emp", "hr"):
        refused = await client.put(url, json=body, headers=as_user(m.people[who], m.org))
        assert refused.status_code == 409, who
    hr_read = await client.get(url, headers=as_user(m.people["hr"], m.org))
    assert hr_read.status_code == 200 and hr_read.json()["keep"] == "a"
    stranger = as_user(m.people["stranger"], m.org)
    assert (await client.get(url, headers=stranger)).status_code == 404
    assert (await client.put(url, json=body, headers=stranger)).status_code == 404


async def test_the_team_list_counts_check_ins_and_follows_the_reporting_line(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    mgr = as_user(m.people["mgr"], m.org)
    rows = (await client.get(f"{FEEDBACK}/team", headers=mgr)).json()
    assert sorted(r["person_name"] for r in rows) == ["Meena", "Priya"]
    assert all(r["check_ins"] == 1 and r["status"] == "open" for r in rows)
    assert (
        await client.get(f"{FEEDBACK}/team", headers=as_user(m.people["emp"], m.org))
    ).json() == []
    # Priya moves to another manager: her open item goes with her.
    moved = await client.put(
        f"/api/v1/employees/{m.people['emp']}/managers",
        json={"managers": [{"user_id": str(m.people["stranger"]), "is_primary": True}]},
        headers=as_user(m.people["hr"], m.org),
    )
    assert moved.status_code == 200, moved.text
    left = (await client.get(f"{FEEDBACK}/team", headers=mgr)).json()
    assert [r["person_name"] for r in left] == ["Meena"]
    new_mgr = as_user(m.people["stranger"], m.org)
    taken = (await client.get(f"{FEEDBACK}/team", headers=new_mgr)).json()
    assert [r["person_name"] for r in taken] == ["Priya"]


async def test_quarterly_feedback_with_goal_statuses(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    org, ids, _ = await setup_org(pg_session_factory, "Hr", "Ravi", "Priya")
    hr_id, mgr_id, emp_id = ids
    await give_role(pg_session_factory, org, hr_id, "hr")
    await report_to(pg_session_factory, org, emp_id, mgr_id)
    hr = as_user(hr_id, org)
    settings = (await client.get("/api/v1/appraisals/settings", headers=hr)).json()
    settings |= {
        "review_period": "half_yearly",
        "checkin_cadence": "monthly",
        "feedback_cadence": "quarterly",
    }
    assert (
        await client.put("/api/v1/appraisals/settings", json=settings, headers=hr)
    ).status_code == 200
    cycle = (
        await client.post(
            "/api/v1/appraisals/cycles",
            json={"period_start": "2026-07-01", "ai_drafting": False},
            headers=hr,
        )
    ).json()
    assert (
        await client.post(f"/api/v1/appraisals/cycles/{cycle['id']}/activate", headers=hr)
    ).status_code == 200
    profile_id = await _profile(pg_session_factory, org, emp_id)
    async with pg_session_factory() as db:
        goal = AppraisalGoal(
            org_id=org,
            profile_id=profile_id,
            cycle_id=uuid.UUID(cycle["id"]),
            target_period_start=date(2026, 7, 1),
            position=1,
            origin=GoalOrigin.EMPLOYEE_OWN,
            status=GoalStatus.ACCEPTED,
        )
        crypto.seal(goal, "title", "Organic clicks +25%")
        db.add(goal)
        await db.commit()
    await run_tick(pg_session_factory, org, datetime(2026, 10, 1, 6, tzinfo=UTC))
    (item,) = await _items(pg_session_factory, org)
    assert (item.period_start, item.period_end) == (date(2026, 7, 1), date(2026, 9, 30))
    mgr = as_user(mgr_id, org)
    url = f"{FEEDBACK}/{item.id}"
    bad = {
        "keep": "a",
        "try_next": "b",
        "goals": [{"goal_id": str(uuid.uuid4()), "status": "at_risk"}],
    }
    assert (await client.put(url, json=bad, headers=mgr)).status_code == 422
    good = {
        "keep": "Steady articles",
        "try_next": "Ship the refresh",
        "goals": [{"goal_id": str(goal.id), "status": "at_risk", "note": "Behind in Sept"}],
    }
    saved = (await client.put(url, json=good, headers=mgr)).json()
    assert saved["goals"] == [
        {
            "id": str(goal.id),
            "title": "Organic clicks +25%",
            "status": "at_risk",
            "note": "Behind in Sept",
        }
    ]
    # The quarter that ends with the review period gets no item: the review covers it.
    await run_tick(pg_session_factory, org, datetime(2027, 1, 4, 6, tzinfo=UTC))
    assert len(await _items(pg_session_factory, org)) == 1
    assert (await _items(pg_session_factory, org))[0].status is FeedbackStatus.OPEN


async def test_monthly_items_refuse_goal_statuses(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    item = await _emp_item(pg_session_factory, m)
    body = {
        "keep": "a",
        "try_next": "b",
        "goals": [{"goal_id": str(uuid.uuid4()), "status": "on_track"}],
    }
    refused = await client.put(
        f"{FEEDBACK}/{item.id}", json=body, headers=as_user(m.people["mgr"], m.org)
    )
    assert refused.status_code == 422
    assert NOV_2.date() < item.due_on
