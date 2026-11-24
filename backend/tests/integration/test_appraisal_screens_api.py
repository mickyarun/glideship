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

"""The reads behind the new screens: the team table, my notes, HR's cycle page."""

from pathlib import Path

import pytest
from httpx import AsyncClient

from app.services.appraisals import hr_remind
from app.services.file_storage import FileStorage
from tests.integration.appraisal_month import october, send_check_in
from tests.integration.appraisal_review_support import BASE, cycle_id
from tests.integration.board_notify_support import Slack, fake_slack, link_slack
from tests.integration.hr_support import configure_hr_storage
from tests.integration.leave_support import Factory, as_user

pytestmark = pytest.mark.integration
FEEDBACK = "/api/v1/manager-feedback"


@pytest.fixture
def hr_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FileStorage:
    """The shared test HR key (see ``hr_support``)."""
    return configure_hr_storage(monkeypatch, tmp_path)


async def test_the_team_table_shows_each_month_as_a_manager_may_see_it(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    await send_check_in(client, m, "emp")
    mgr = as_user(m.people["mgr"], m.org)
    rows = {
        r["person_name"]: r
        for r in (await client.get(f"{BASE}/team-overview", headers=mgr)).json()
    }
    assert [mo["state"] for mo in rows["Priya"]["months"]] == ["sent", "not_open", "not_open"]
    # Meena's October is past due and unsent: late, never "written in".
    assert rows["Meena"]["months"][0]["state"] == "late"
    (note,) = rows["Priya"]["notes"]
    assert not note["sent"] and note["due_on"] is not None
    assert (
        await client.get(f"{BASE}/team-overview", headers=as_user(m.people["emp"], m.org))
    ).json() == []


async def test_my_notes_are_only_the_sent_ones(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    emp, mgr = as_user(m.people["emp"], m.org), as_user(m.people["mgr"], m.org)
    rows = (await client.get(f"{FEEDBACK}/team", headers=mgr)).json()
    item = next(r for r in rows if r["person_name"] == "Priya")
    url = f"{FEEDBACK}/{item['id']}"
    await client.put(url, json={"keep": "Clear PRs", "try_next": "Pair on UAT"}, headers=mgr)
    assert (await client.get(f"{FEEDBACK}/mine", headers=emp)).json() == []
    await client.post(f"{url}/send", headers=mgr)
    (mine,) = (await client.get(f"{FEEDBACK}/mine", headers=emp)).json()
    assert (mine["keep"], mine["manager_name"]) == ("Clear PRs", "Ravi")


async def test_hr_sees_goals_months_and_late_counts_and_can_remind_once_a_day(
    client: AsyncClient,
    pg_session_factory: Factory,
    hr_key: FileStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    m = await october(client, pg_session_factory)
    slack: Slack = fake_slack(monkeypatch, pg_session_factory)
    await link_slack(pg_session_factory, m.org, m.people["emp"], m.people["quiet"])
    hr = as_user(m.people["hr"], m.org)
    cycle = await cycle_id(client, m)
    progress = (await client.get(f"{BASE}/cycles/{cycle}/progress", headers=hr)).json()
    assert progress["min_goals"] == 3
    october_counts = progress["check_in_periods"][0]
    assert (october_counts["sent"], october_counts["total"]) == (0, 2)
    # Two late check-ins, and Ravi: nobody has goals and the goals date has passed.
    assert progress["remind_count"] == 3 and progress["reminded_at"] is None
    priya = next(p for p in progress["people"] if p["name"] == "Priya")
    assert priya["months"][0] == "late" and priya["manager_user_id"] == str(m.people["mgr"])
    sent = await client.post(f"{BASE}/cycles/{cycle}/remind", headers=hr)
    assert sent.status_code == 200 and sent.json()["people"] == 3
    assert all("check-in was due" in text for _, text in await slack.flush())
    again = await client.post(f"{BASE}/cycles/{cycle}/remind", headers=hr)
    assert again.status_code == 409
    after = (await client.get(f"{BASE}/cycles/{cycle}/progress", headers=hr)).json()
    assert after["reminded_at"] is not None and after["reminded_today"]
    assert hr_remind is not None
