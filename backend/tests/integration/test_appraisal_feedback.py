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

"""Manager notes: items opening on the tick, who reads and writes them, sending, due dates."""

import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import FeedbackStatus, GoalOrigin, GoalStatus
from app.models.appraisal_goal import AppraisalGoal
from app.models.appraisal_manager_feedback import AppraisalManagerFeedback
from app.models.employee_audit_event import EmployeeAuditAction, EmployeeAuditEvent
from app.repositories.employee_profile import EmployeeProfileRepository
from app.services.appraisals import crypto
from app.services.appraisals.note_clock import date_waiting_notes
from app.services.file_storage import FileStorage
from tests.integration.appraisal_month import NOV_2, Month, october, run_tick, send_check_in
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
    # Nothing to answer yet: a note is due only once its check-in is sent.
    assert {(i.period_start, i.period_end, i.due_on) for i in items} == {
        (date(2026, 10, 1), date(2026, 10, 31), None)
    }
    await run_tick(pg_session_factory, m.org, datetime(2026, 11, 3, 6, tzinfo=UTC))
    assert len(await _items(pg_session_factory, m.org)) == 2


async def test_the_employee_sees_feedback_once_the_manager_sends_it(
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
    assert (await client.get(f"{FEEDBACK}/{item.id}", headers=emp)).status_code == 404
    hr = (await client.get(f"{FEEDBACK}/{item.id}", headers=as_user(m.people["hr"], m.org))).json()
    assert hr["content_hidden"] and hr["keep"] == "" and hr["sent_at"] is None
    await client.put(
        f"{FEEDBACK}/{item.id}",
        json={"keep": "Catching regressions early", "try_next": "Pair on UAT"},
        headers=mgr,
    )
    assert (await client.post(f"{FEEDBACK}/{item.id}/send", headers=mgr)).status_code == 200
    seen = await client.get(f"{FEEDBACK}/{item.id}", headers=emp)
    assert seen.status_code == 200
    assert seen.json()["keep"] == "Catching regressions early"
    assert not seen.json()["can_edit"]
    mine = (await client.get(f"{CHECK_INS}/mine", headers=emp)).json()
    october_check_in = next(c for c in mine if c["period_start"] == "2026-10-01")
    page = (await client.get(f"{CHECK_INS}/{october_check_in['id']}", headers=emp)).json()
    assert page["feedback"]["keep"] == "Catching regressions early"
    assert page["feedback"]["done"] is True
    async with pg_session_factory() as db:
        row = await db.get(AppraisalManagerFeedback, item.id)
        assert row is not None and row.keep_note is not None
        assert b"regressions" not in row.keep_note


async def test_sending_needs_both_lines_and_is_audited(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    item = await _emp_item(pg_session_factory, m)
    mgr = as_user(m.people["mgr"], m.org)
    url = f"{FEEDBACK}/{item.id}"
    await client.put(url, json={"keep": "Clear PRs"}, headers=mgr)
    assert (await client.post(f"{url}/send", headers=mgr)).status_code == 422
    await client.put(url, json={"keep": "Clear PRs", "try_next": "Pair on UAT"}, headers=mgr)
    done = await client.post(f"{url}/send", headers=mgr)
    assert done.status_code == 200 and done.json()["status"] == "done"
    assert done.json()["sent_at"] is not None
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
    # A sent note keeps both lines.
    cleared = await client.put(url, json={"keep": "Clear PRs", "try_next": ""}, headers=mgr)
    assert cleared.status_code == 422


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
    # The person doesn't see an unsent note at all; HR sees it but can't write.
    for who, code in (("emp", 404), ("hr", 409)):
        refused = await client.put(url, json=body, headers=as_user(m.people[who], m.org))
        assert refused.status_code == code, who
    hr = as_user(m.people["hr"], m.org)
    hr_read = await client.get(url, headers=hr)
    assert hr_read.status_code == 200 and hr_read.json()["keep"] == ""
    await client.post(f"{url}/send", headers=as_user(m.people["mgr"], m.org))
    assert (await client.get(url, headers=hr)).json()["keep"] == "a"
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


async def _audits(factory: Factory, org: uuid.UUID, action: EmployeeAuditAction) -> list[str]:
    async with factory() as db:
        rows = await db.scalars(
            select(EmployeeAuditEvent).where(
                EmployeeAuditEvent.org_id == org, EmployeeAuditEvent.action == action
            )
        )
        return [r.target for r in rows]


async def test_edits_after_the_person_could_read_them_are_audited(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    item = await _emp_item(pg_session_factory, m)
    mgr = as_user(m.people["mgr"], m.org)
    url = f"{FEEDBACK}/{item.id}"
    lines = {"keep": "Clear PRs", "try_next": "Pair on UAT"}
    await client.put(url, json=lines, headers=mgr)
    assert await _audits(pg_session_factory, m.org, EmployeeAuditAction.APPRAISAL_CHANGED) == []
    first = (await client.post(f"{url}/send", headers=mgr)).json()
    second = (await client.post(f"{url}/send", headers=mgr)).json()
    assert first["sent_at"] == second["sent_at"]
    given = await _audits(pg_session_factory, m.org, EmployeeAuditAction.APPRAISAL_FEEDBACK_GIVEN)
    assert given == [str(item.id)]
    # Its check-in was sent today, so the note is due in five working days.
    await send_check_in(client, m, "emp")
    edited = await client.put(url, json={**lines, "keep": "Clear PRs early"}, headers=mgr)
    assert edited.json()["status"] == "done" and edited.json()["sent_at"] == first["sent_at"]
    assert edited.json()["edited_after_send_at"] is not None
    changed = await _audits(pg_session_factory, m.org, EmployeeAuditAction.APPRAISAL_CHANGED)
    assert changed == [str(item.id)]
    await client.put(url, json={**lines, "keep": "Clear PRs early"}, headers=mgr)
    assert (
        len(await _audits(pg_session_factory, m.org, EmployeeAuditAction.APPRAISAL_CHANGED)) == 1
    )


async def test_unsent_items_follow_a_new_manager_and_sent_ones_stay(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    mgr = as_user(m.people["mgr"], m.org)
    rows = {
        r["person_name"]: r for r in (await client.get(f"{FEEDBACK}/team", headers=mgr)).json()
    }
    done_url = f"{FEEDBACK}/{rows['Meena']['id']}"
    await client.put(done_url, json={"keep": "a", "try_next": "b"}, headers=mgr)
    await client.post(f"{done_url}/send", headers=mgr)
    priya_draft = f"{FEEDBACK}/{rows['Priya']['id']}"
    await client.put(priya_draft, json={"keep": "unsent", "try_next": "draft"}, headers=mgr)
    hr = as_user(m.people["hr"], m.org)
    for who in ("emp", "quiet"):
        moved = await client.put(
            f"/api/v1/employees/{m.people[who]}/managers",
            json={"managers": [{"user_id": str(m.people["stranger"]), "is_primary": True}]},
            headers=hr,
        )
        assert moved.status_code == 200, moved.text
    by_id = {i.id: i for i in await _items(pg_session_factory, m.org)}
    assert by_id[uuid.UUID(rows["Priya"]["id"])].manager_user_id == m.people["stranger"]
    assert by_id[uuid.UUID(rows["Meena"]["id"])].manager_user_id == m.people["mgr"]
    new_mgr = as_user(m.people["stranger"], m.org)
    priya = f"{FEEDBACK}/{rows['Priya']['id']}"
    # The old manager's unsent draft doesn't travel with the item.
    assert (await client.get(priya, headers=new_mgr)).json()["keep"] == ""
    taken = await client.put(priya, json={"keep": "x", "try_next": "y"}, headers=new_mgr)
    assert taken.status_code == 200
    assert (await client.put(priya, json={"keep": "z"}, headers=mgr)).status_code == 404


async def _pin(factory: Factory, org: uuid.UUID, opened: datetime, **check_in: object) -> None:
    """Pin when the notes opened, and set fields on the check-ins, so dates don't drift."""
    async with factory() as db:
        await db.execute(
            update(AppraisalManagerFeedback)
            .where(AppraisalManagerFeedback.org_id == org)
            .values(created_at=opened, due_on=None)
        )
        if check_in:
            await db.execute(
                update(AppraisalCheckIn).where(AppraisalCheckIn.org_id == org).values(**check_in)
            )
        await db.commit()


async def test_a_note_opening_after_its_check_in_was_sent_is_due_from_the_opening(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    sent = datetime(2026, 11, 6, 15, tzinfo=UTC)
    await _pin(pg_session_factory, m.org, datetime(2026, 11, 9, 6, tzinfo=UTC), sent_at=sent)
    await run_tick(pg_session_factory, m.org, datetime(2026, 11, 10, 6, tzinfo=UTC))
    # Opened Monday 9 Nov, after Friday's send: five working days from the opening.
    assert {i.due_on for i in await _items(pg_session_factory, m.org)} == {date(2026, 11, 16)}


async def test_a_check_in_opens_due_five_working_days_after_its_month(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    async with pg_session_factory() as db:
        rows = list(
            await db.scalars(select(AppraisalCheckIn).where(AppraisalCheckIn.org_id == m.org))
        )
    # October ends on Saturday the 31st: Monday 2 to Friday 6 November.
    assert {(c.due_on, c.sent_at) for c in rows} == {(date(2026, 11, 6), None)}


async def test_a_sent_but_unfinished_note_follows_a_new_manager_with_its_words(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    item = await _emp_item(pg_session_factory, m)
    mgr = as_user(m.people["mgr"], m.org)
    url = f"{FEEDBACK}/{item.id}"
    await client.put(url, json={"keep": "Clear PRs"}, headers=mgr)
    async with pg_session_factory() as db:
        # As the migration leaves a note written before sending existed.
        await db.execute(
            update(AppraisalManagerFeedback)
            .where(AppraisalManagerFeedback.id == item.id)
            .values(sent_at=datetime.now(UTC), due_on=date(2099, 1, 1))
        )
        await db.commit()
    moved = await client.put(
        f"/api/v1/employees/{m.people['emp']}/managers",
        json={"managers": [{"user_id": str(m.people["stranger"]), "is_primary": True}]},
        headers=as_user(m.people["hr"], m.org),
    )
    assert moved.status_code == 200, moved.text
    new_mgr = as_user(m.people["stranger"], m.org)
    taken = (await client.get(url, headers=new_mgr)).json()
    assert taken["can_edit"] and taken["keep"] == "Clear PRs"
    await client.put(url, json={"keep": "Clear PRs", "try_next": "Pair on UAT"}, headers=new_mgr)
    finished = await client.post(f"{url}/send", headers=new_mgr)
    assert finished.json()["status"] == "done"


async def test_a_note_whose_check_in_closes_unsent_is_due_from_the_close(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    assert {i.due_on for i in await _items(pg_session_factory, m.org)} == {None}
    await _pin(pg_session_factory, m.org, NOV_2)
    # November's check-in opens on Tuesday 1 December, closing October's unsent.
    await run_tick(pg_session_factory, m.org, datetime(2026, 12, 1, 6, tzinfo=UTC))
    october_items = [
        i for i in await _items(pg_session_factory, m.org) if i.period_end == date(2026, 10, 31)
    ]
    assert {i.due_on for i in october_items} == {date(2026, 12, 8)}


async def test_a_send_the_opening_tick_missed_is_dated_on_the_next_one(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    emp_profile = await _profile(pg_session_factory, m.org, m.people["emp"])
    await _pin(pg_session_factory, m.org, NOV_2)
    async with pg_session_factory() as db:
        # Committed without dating the note, as when the send crosses the tick
        # that opens it: the send can't see the note, the tick can't see the send.
        await db.execute(
            update(AppraisalCheckIn)
            .where(AppraisalCheckIn.profile_id == emp_profile)
            .values(sent_at=datetime(2026, 11, 3, 10, tzinfo=UTC))
        )
        await db.commit()
    await run_tick(pg_session_factory, m.org, datetime(2026, 11, 4, 6, tzinfo=UTC))
    due = {i.profile_id: i.due_on for i in await _items(pg_session_factory, m.org)}
    assert due[emp_profile] == date(2026, 11, 10)
    assert [d for p, d in due.items() if p != emp_profile] == [None]


async def test_the_note_clock_counts_in_the_orgs_own_days(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    # 23:30 UTC on Monday 30 Nov is already Tuesday 1 Dec in India.
    closed = datetime(2026, 11, 30, 23, 30, tzinfo=UTC)
    await _pin(pg_session_factory, m.org, NOV_2, closed_at=closed)
    async with pg_session_factory() as db:
        cycle = await db.scalar(select(AppraisalCycle).where(AppraisalCycle.org_id == m.org))
        assert cycle is not None
        dated = await date_waiting_notes(db, cycle, date(2026, 12, 1), ZoneInfo("Asia/Kolkata"))
        await db.commit()
    assert dated == 2
    assert {i.due_on for i in await _items(pg_session_factory, m.org)} == {date(2026, 12, 8)}


async def _yearly_with_quarterly_notes(
    client: AsyncClient, factory: Factory, *, report_first: bool
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """A 2026 yearly cycle with monthly check-ins and quarterly notes; (org, emp, mgr)."""
    org, ids, _ = await setup_org(factory, "Hr", "Ravi", "Priya")
    hr_id, mgr_id, emp_id = ids
    await give_role(factory, org, hr_id, "hr")
    if report_first:
        await report_to(factory, org, emp_id, mgr_id)
    hr = as_user(hr_id, org)
    settings = (await client.get("/api/v1/appraisals/settings", headers=hr)).json()
    settings |= {
        "review_period": "yearly",
        "checkin_cadence": "monthly",
        "feedback_cadence": "quarterly",
    }
    assert (
        await client.put("/api/v1/appraisals/settings", json=settings, headers=hr)
    ).status_code == 200
    body = {"period_start": "2026-01-01", "ai_drafting": False}
    cycle = (await client.post("/api/v1/appraisals/cycles", json=body, headers=hr)).json()
    activated = await client.post(f"/api/v1/appraisals/cycles/{cycle['id']}/activate", headers=hr)
    assert activated.status_code == 200, activated.text
    return org, emp_id, mgr_id


async def test_a_late_joiners_note_with_no_matching_check_in_is_still_dated(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    org, emp_id, mgr_id = await _yearly_with_quarterly_notes(
        client, pg_session_factory, report_first=False
    )
    # Enrolled on 1 May, inside the cut-off: April's check-in opens, but the
    # note opens for Q1, which ended with March. No check-in will match it.
    await report_to(pg_session_factory, org, emp_id, mgr_id)
    await run_tick(pg_session_factory, org, datetime(2026, 5, 1, 6, tzinfo=UTC))
    (item,) = await _items(pg_session_factory, org)
    assert item.period_end == date(2026, 3, 31) and item.due_on is not None


async def test_a_mid_quarter_leavers_note_is_still_dated(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    org, emp_id, _ = await _yearly_with_quarterly_notes(
        client, pg_session_factory, report_first=True
    )
    async with pg_session_factory() as db:
        profile = await EmployeeProfileRepository(db, org_id=org).get_by_user(emp_id)
        assert profile is not None
        # Left in February: March's check-in never opens, Q1's note does.
        profile.date_of_exit = date(2026, 2, 15)
        await db.commit()
    await run_tick(pg_session_factory, org, datetime(2026, 4, 1, 6, tzinfo=UTC))
    (item,) = await _items(pg_session_factory, org)
    assert item.period_end == date(2026, 3, 31) and item.due_on is not None
