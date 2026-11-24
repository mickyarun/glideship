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

"""Who the team table and HR's reminder count: leavers, withdrawn people, second managers."""

from datetime import date
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.models.appraisal import Appraisal
from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import AppraisalStatus
from app.models.appraisal_manager_feedback import AppraisalManagerFeedback
from app.models.employee_reporting_manager import EmployeeReportingManager
from app.repositories.employee_profile import EmployeeProfileRepository
from app.services.file_storage import FileStorage
from tests.integration.appraisal_month import Month, october, send_check_in
from tests.integration.appraisal_review_support import BASE, cycle_id
from tests.integration.board_notify_support import Slack, fake_slack, link_slack
from tests.integration.hr_support import configure_hr_storage
from tests.integration.leave_support import Factory, as_user

pytestmark = pytest.mark.integration


@pytest.fixture
def hr_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FileStorage:
    """The shared test HR key (see ``hr_support``)."""
    return configure_hr_storage(monkeypatch, tmp_path)


async def _leaves(factory: Factory, m: Month, who: str) -> None:
    async with factory() as db:
        profile = await EmployeeProfileRepository(db, org_id=m.org).get_by_user(m.people[who])
        assert profile is not None
        profile.date_of_exit = date(2026, 11, 2)
        await db.commit()


async def _notes_overdue(factory: Factory, m: Month) -> None:
    async with factory() as db:
        await db.execute(
            update(AppraisalManagerFeedback)
            .where(AppraisalManagerFeedback.org_id == m.org)
            .values(due_on=date(2026, 11, 10))
        )
        await db.commit()


async def test_the_team_table_leaves_out_leavers_and_the_withdrawn_and_others_notes(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    await _leaves(pg_session_factory, m, "quiet")
    async with pg_session_factory() as db:
        profile = await EmployeeProfileRepository(db, org_id=m.org).get_by_user(m.people["emp"])
        assert profile is not None
        db.add(
            EmployeeReportingManager(
                org_id=m.org,
                profile_id=profile.id,
                manager_user_id=m.people["stranger"],
                is_primary=False,
            )
        )
        await db.commit()
    mgr = as_user(m.people["mgr"], m.org)
    (row,) = (await client.get(f"{BASE}/team-overview", headers=mgr)).json()
    assert row["person_name"] == "Priya" and len(row["notes"]) == 1
    assert row["min_goals"] == 3 and row["max_goals"] >= 3
    second = as_user(m.people["stranger"], m.org)
    rows = (await client.get(f"{BASE}/team-overview", headers=second)).json()
    # A second manager sees the person but holds none of the first's notes.
    assert [(r["person_name"], r["notes"]) for r in rows] == [("Priya", [])]
    async with pg_session_factory() as db:
        await db.execute(
            update(Appraisal)
            .where(Appraisal.org_id == m.org)
            .values(status=AppraisalStatus.WITHDRAWN)
        )
        await db.commit()
    assert (await client.get(f"{BASE}/team-overview", headers=mgr)).json() == []


async def test_hr_reminds_exactly_the_people_the_page_counts(
    client: AsyncClient,
    pg_session_factory: Factory,
    hr_key: FileStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    m = await october(client, pg_session_factory)
    slack: Slack = fake_slack(monkeypatch, pg_session_factory)
    slack_ids = await link_slack(
        pg_session_factory, m.org, m.people["emp"], m.people["quiet"], m.people["mgr"]
    )
    await send_check_in(client, m, "emp")
    await _notes_overdue(pg_session_factory, m)
    await _leaves(pg_session_factory, m, "quiet")
    hr = as_user(m.people["hr"], m.org)
    cycle = await cycle_id(client, m)
    progress = (await client.get(f"{BASE}/cycles/{cycle}/progress", headers=hr)).json()
    meena = next(p for p in progress["people"] if p["name"] == "Meena")
    assert meena["check_ins_late"] == 0 and meena["feedback_overdue"] == 0
    # Only Ravi is late: his note on Priya's sent check-in. Meena has left.
    assert progress["remind_count"] == 1
    sent = (await client.post(f"{BASE}/cycles/{cycle}/remind", headers=hr)).json()
    assert sent["people"] == progress["remind_count"]
    ((user, text),) = await slack.flush()
    assert user == slack_ids[m.people["mgr"]] and "check-in was due" not in text


async def test_hr_reminds_only_a_running_cycle_and_only_when_someone_is_late(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    hr = as_user(m.people["hr"], m.org)
    cycle = await cycle_id(client, m)
    async with pg_session_factory() as db:
        await db.execute(
            update(AppraisalCheckIn)
            .where(AppraisalCheckIn.org_id == m.org)
            .values(due_on=date(2099, 1, 1))
        )
        await db.execute(
            update(AppraisalCycle)
            .where(AppraisalCycle.org_id == m.org)
            .values(goals_due=date(2026, 12, 31))
        )
        await db.commit()
    # Nobody is late: nothing goes out, and the day isn't used up.
    quiet = await client.post(f"{BASE}/cycles/{cycle}/remind", headers=hr)
    assert quiet.json() == {"people": 0, "reached": 0}
    progress = (await client.get(f"{BASE}/cycles/{cycle}/progress", headers=hr)).json()
    assert progress["reminded_at"] is None and not progress["reminded_today"]
    await client.post(f"{BASE}/cycles/{cycle}/close", headers=hr)
    closed = await client.post(f"{BASE}/cycles/{cycle}/remind", headers=hr)
    assert closed.status_code == 409
