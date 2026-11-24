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

"""Sending check-ins: unsent writing stays the person's, late is past due and unsent,
and the migration's backfill keeps everything readable that was readable before."""

import importlib.util
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import ModuleType

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text, update

from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_manager_feedback import AppraisalManagerFeedback
from app.services.appraisals.work_calendar import WorkCalendar
from app.services.file_storage import FileStorage
from tests.integration.appraisal_month import october, send_check_in
from tests.integration.appraisal_review_support import BASE, end_period_early, team_ids
from tests.integration.hr_support import configure_hr_storage
from tests.integration.leave_support import Factory, as_user

pytestmark = pytest.mark.integration
CHECK_INS = "/api/v1/check-ins"
MIGRATION = "6d2d593be9c9_appraisal_send_due_dates_and_open_.py"
NOTE = {"lines": {"team": ["Paired on the refunds API"]}, "blocking": "", "next_month": ""}
LINK = {"url": "https://doc.test/spec", "title": "Refunds spec", "heading": "team"}


@pytest.fixture
def hr_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FileStorage:
    """The shared test HR key (see ``hr_support``)."""
    return configure_hr_storage(monkeypatch, tmp_path)


def _migration() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / MIGRATION
    spec = importlib.util.spec_from_file_location("send_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def test_an_unsent_check_in_shows_its_facts_but_not_the_persons_words(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    emp = as_user(m.people["emp"], m.org)
    mine = (await client.get(f"{CHECK_INS}/mine", headers=emp)).json()
    url = f"{CHECK_INS}/{mine[0]['id']}"
    await client.put(f"{url}/note", json=NOTE, headers=emp)
    assert (await client.post(f"{url}/links", json=LINK, headers=emp)).status_code == 201
    own = (await client.get(url, headers=emp)).json()
    assert own["note"]["lines"]["team"] and own["links"] and own["can_send"]
    assert own["status"] == "employee_added"
    for who in ("mgr", "hr"):
        theirs = (await client.get(url, headers=as_user(m.people[who], m.org))).json()
        assert theirs["content_hidden"], who
        # Nor can they tell the person has written in it.
        assert theirs["status"] == "open", who
        assert theirs["note"]["lines"] == {} and theirs["links"] == [], who
        assert theirs["facts"], who
        assert not theirs["can_send"], who
    # Only the person sends it, and only once.
    assert (
        await client.post(f"{url}/send", headers=as_user(m.people["mgr"], m.org))
    ).status_code == 404
    assert (await client.post(f"{url}/send", headers=emp)).status_code == 200
    assert (await client.post(f"{url}/send", headers=emp)).status_code == 409
    read = (await client.get(url, headers=as_user(m.people["mgr"], m.org))).json()
    assert not read["content_hidden"]
    assert read["note"]["lines"]["team"] == ["Paired on the refunds API"]
    assert [link["title"] for link in read["links"]] == ["Refunds spec"]


async def test_late_is_past_due_and_unsent_and_edits_after_sending_stop_at_the_due_date(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    emp = as_user(m.people["emp"], m.org)
    mine = (await client.get(f"{CHECK_INS}/mine", headers=emp)).json()
    url = f"{CHECK_INS}/{mine[0]['id']}"
    # Due Friday 6 November, well behind today.
    assert mine[0]["due_on"] == "2026-11-06" and mine[0]["late"]
    await send_check_in(client, m, "emp")
    after = (await client.get(url, headers=emp)).json()
    assert not after["late"] and not after["can_edit"]
    assert (await client.put(f"{url}/note", json=NOTE, headers=emp)).status_code == 409
    async with pg_session_factory() as db:
        await db.execute(
            update(AppraisalCheckIn)
            .where(AppraisalCheckIn.id == uuid.UUID(url.rsplit("/", 1)[1]))
            .values(due_on=datetime.now(UTC).date() + timedelta(days=7))
        )
        await db.commit()
    edited = await client.put(f"{url}/note", json=NOTE, headers=emp)
    assert edited.status_code == 200
    assert edited.json()["edited_after_send_at"] is not None
    # The note answering it is now due, five working days from today.
    async with pg_session_factory() as db:
        dues = [
            i.due_on
            for i in await db.scalars(
                select(AppraisalManagerFeedback).where(AppraisalManagerFeedback.org_id == m.org)
            )
        ]
    assert sorted(d is None for d in dues) == [False, True]


async def test_the_review_hides_unsent_months_from_the_manager(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    emp, mgr = as_user(m.people["emp"], m.org), as_user(m.people["mgr"], m.org)
    mine = (await client.get(f"{CHECK_INS}/mine", headers=emp)).json()
    url = f"{CHECK_INS}/{mine[0]['id']}"
    await client.put(f"{url}/note", json=NOTE, headers=emp)
    link = (await client.post(f"{url}/links", json=LINK, headers=emp)).json()["links"][0]
    ids = await team_ids(client, m)
    cycle = (await client.get(f"{BASE}/cycles", headers=as_user(m.people["hr"], m.org))).json()
    await end_period_early(pg_session_factory, m.org)
    started = await client.post(
        f"{BASE}/cycles/{cycle[0]['id']}/start-review", headers=as_user(m.people["hr"], m.org)
    )
    assert started.status_code == 202
    review = f"{BASE}/{ids['Priya']}"
    (month,) = (await client.get(review, headers=mgr)).json()["timeline"]
    assert not month["sent"] and month["note"]["lines"] == {} and month["links"] == []
    assert month["status"] == "open"
    hr_view = await client.get(review, headers=as_user(m.people["hr"], m.org))
    assert [t["status"] for t in hr_view.json()["timeline"]] == ["open"]
    (own,) = (await client.get(review, headers=emp)).json()["timeline"]
    assert own["links"] and own["note"]["lines"]
    # Nobody cites a link from a check-in that was never sent: the reader can't open it.
    cite = {"band": 3, "evidence": [f"link:{link['id']}"], "goals": []}
    assert (await client.put(f"{review}/self", json=cite, headers=emp)).status_code == 422
    assert (
        await client.put(f"{review}/self", json={**cite, "evidence": []}, headers=emp)
    ).status_code == 200
    assert (await client.post(f"{review}/self/submit", headers=emp)).status_code == 200
    change = {"agree": False, "band": 4, "reason": "Late", "evidence": cite["evidence"]}
    assert (await client.put(f"{review}/manager", json=change, headers=mgr)).status_code == 422


async def test_the_backfill_marks_existing_writing_sent_and_keeps_due_dates(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    mgr = as_user(m.people["mgr"], m.org)
    rows = (await client.get("/api/v1/manager-feedback/team", headers=mgr)).json()
    written = next(r for r in rows if r["person_name"] == "Priya")
    await client.put(
        f"/api/v1/manager-feedback/{written['id']}", json={"keep": "Clear PRs"}, headers=mgr
    )
    kept_due = date(2026, 11, 10)
    async with pg_session_factory() as db:
        # As the rows stood before sending existed: nothing sent, notes due by period.
        await db.execute(
            update(AppraisalCheckIn)
            .where(AppraisalCheckIn.org_id == m.org)
            .values(sent_at=None, due_on=None)
        )
        await db.execute(
            update(AppraisalManagerFeedback)
            .where(AppraisalManagerFeedback.org_id == m.org)
            .values(sent_at=None, due_on=kept_due)
        )
        for statement in _migration().BACKFILL:
            await db.execute(text(statement))
        await db.commit()
        check_ins = list(
            await db.scalars(select(AppraisalCheckIn).where(AppraisalCheckIn.org_id == m.org))
        )
        notes = {
            str(i.id): i
            for i in await db.scalars(
                select(AppraisalManagerFeedback).where(AppraisalManagerFeedback.org_id == m.org)
            )
        }
    # Still open, so still being written: at least five weekdays from today.
    fresh = WorkCalendar().shift(datetime.now(UTC).date(), 5)
    assert all(c.sent_at == c.updated_at for c in check_ins)
    assert {c.due_on for c in check_ins} == {max(date(2026, 11, 6), fresh)}
    assert notes[written["id"]].sent_at is not None
    assert [n.sent_at for k, n in notes.items() if k != written["id"]] == [None]
    # The half-written note gets the same fresh window; the untouched one keeps its date.
    assert notes[written["id"]].due_on == max(kept_due, fresh)
    assert [n.due_on for k, n in notes.items() if k != written["id"]] == [kept_due]
    # The person reads the written note, as they could before.
    emp = as_user(m.people["emp"], m.org)
    seen = await client.get(f"/api/v1/manager-feedback/{written['id']}", headers=emp)
    assert seen.status_code == 200 and seen.json()["keep"] == "Clear PRs"
    # The manager can still finish it and send it.
    note_url = f"/api/v1/manager-feedback/{written['id']}"
    both = {"keep": "Clear PRs", "try_next": "Pair on UAT"}
    assert (await client.put(note_url, json=both, headers=mgr)).status_code == 200
    finished = await client.post(f"{note_url}/send", headers=mgr)
    assert finished.json()["status"] == "done"
    # And the person can keep writing the open check-in.
    mine = (await client.get(f"{CHECK_INS}/mine", headers=emp)).json()
    note = await client.put(f"{CHECK_INS}/{mine[0]['id']}/note", json=NOTE, headers=emp)
    assert note.status_code == 200


async def test_goal_values_across_months_show_only_sent_check_ins_to_others(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    emp, mgr = as_user(m.people["emp"], m.org), as_user(m.people["mgr"], m.org)
    ids = await team_ids(client, m)
    goals_url = f"{BASE}/{ids['Priya']}/goals"
    added = await client.post(
        goals_url, json={"title": "p95 under 300 ms", "reason": "Q4"}, headers=mgr
    )
    goal_id = next(g["id"] for g in added.json()["goals"] if g["status"] == "accepted")
    check_in_id = (await client.get(f"{CHECK_INS}/mine", headers=emp)).json()[0]["id"]
    value = {"value": "410 ms", "source_note": "Dashboard", "source_url": None}
    put = await client.put(
        f"{CHECK_INS}/{check_in_id}/goal-values/{goal_id}", json=value, headers=emp
    )
    assert put.status_code == 200, put.text
    url = f"{BASE}/{ids['Priya']}/goal-values"
    (own,) = (await client.get(url, headers=emp)).json()
    assert [(v["period_start"], v["value"]) for v in own["values"]] == [("2026-10-01", "410 ms")]
    (theirs,) = (await client.get(url, headers=mgr)).json()
    assert theirs["title"] == "p95 under 300 ms" and theirs["values"] == []
    await send_check_in(client, m, "emp")
    (sent,) = (await client.get(url, headers=mgr)).json()
    assert [v["value"] for v in sent["values"]] == ["410 ms"]
    stranger = as_user(m.people["stranger"], m.org)
    assert (await client.get(url, headers=stranger)).status_code == 404
