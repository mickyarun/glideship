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

"""Monthly check-ins end to end: the tick, the fact rules, writes, access, closing."""

import uuid
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_enums import CheckInStatus, DraftStatus
from app.services.file_storage import FileStorage
from tests.integration.appraisal_month import NOV_2, Month, october, run_tick
from tests.integration.hr_support import configure_hr_storage
from tests.integration.leave_support import (
    Factory,
    as_user,
)

pytestmark = pytest.mark.integration
DEC_2 = datetime(2026, 12, 2, 6, tzinfo=UTC)
CHECK_INS = "/api/v1/check-ins"


@pytest.fixture
def hr_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FileStorage:
    """The shared test HR key (see ``hr_support``)."""
    return configure_hr_storage(monkeypatch, tmp_path)


async def _check_in_id(client: AsyncClient, m: Month, who: str) -> str:
    mine = (await client.get(f"{CHECK_INS}/mine", headers=as_user(m.people[who], m.org))).json()
    assert len(mine) == 1 and mine[0]["period_start"] == "2026-10-01"
    return str(mine[0]["id"])


async def test_tick_lists_only_cards_still_done_in_the_month(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    await run_tick(pg_session_factory, m.org, NOV_2)  # a second pass changes nothing
    async with pg_session_factory() as db:
        rows = list(
            await db.scalars(select(AppraisalCheckIn).where(AppraisalCheckIn.org_id == m.org))
        )
    mine = [r for r in rows if r.period_start == date(2026, 10, 1)]
    # Only Priya and Meena have a primary manager, so only they are enrolled.
    assert len(mine) == 2
    emp = next(r for r in mine if r.fact_refs)
    assert [f["id"] for f in emp.fact_refs] == [str(m.counted)]
    assert emp.available_days == emp.working_days - 2
    assert emp.draft_status is DraftStatus.NONE


async def test_employee_writes_until_it_closes(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    me = as_user(m.people["emp"], m.org)
    check_in = await _check_in_id(client, m, "emp")
    note = {"lines": {"team": ["Covered support during the launch"]}, "blocking": "Access logs"}
    saved = await client.put(f"{CHECK_INS}/{check_in}/note", json=note, headers=me)
    assert saved.status_code == 200 and saved.json()["status"] == "employee_added"
    tag = {str(m.counted): {"heading": "delivery_quality"}}
    assert (
        await client.put(f"{CHECK_INS}/{check_in}/fact-tags", json=tag, headers=me)
    ).status_code == 200
    stray = {str(uuid.uuid4()): {"heading": "team"}}
    assert (
        await client.put(f"{CHECK_INS}/{check_in}/fact-tags", json=stray, headers=me)
    ).status_code == 422
    link = {"url": "https://example.com/report", "title": "Report", "heading": "initiative"}
    for _ in range(5):
        assert (
            await client.post(f"{CHECK_INS}/{check_in}/links", json=link, headers=me)
        ).status_code == 201
    assert (
        await client.post(f"{CHECK_INS}/{check_in}/links", json=link, headers=me)
    ).status_code == 409
    goal = await client.put(
        f"{CHECK_INS}/{check_in}/goal-values/{uuid.uuid4()}", json={"value": "6"}, headers=me
    )
    assert goal.status_code == 404
    read = (await client.get(f"{CHECK_INS}/{check_in}", headers=me)).json()
    assert read["note"]["lines"] == {"team": ["Covered support during the launch"]}
    assert len(read["links"]) == 5 and read["can_edit"]


async def test_manager_reads_but_never_writes_and_others_get_nothing(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    check_in = await _check_in_id(client, m, "emp")
    manager = as_user(m.people["mgr"], m.org)
    read = await client.get(f"{CHECK_INS}/{check_in}", headers=manager)
    assert read.status_code == 200
    # The card is on a members-only board the manager isn't on.
    fact = read.json()["facts"][0]
    assert fact["private"] and fact["title"] is None and fact["key"] == "private record · Board"
    assert not read.json()["can_edit"]
    note = {"lines": {}, "blocking": "written by the manager"}
    assert (
        await client.put(f"{CHECK_INS}/{check_in}/note", json=note, headers=manager)
    ).status_code == 404
    stranger = as_user(m.people["stranger"], m.org)
    assert (await client.get(f"{CHECK_INS}/{check_in}", headers=stranger)).status_code == 404
    team = (await client.get(f"{CHECK_INS}/team", headers=manager)).json()
    assert {row["person_name"] for row in team} == {"Priya", "Meena"}


async def test_check_in_closes_when_the_next_opens(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    me = as_user(m.people["emp"], m.org)
    check_in = await _check_in_id(client, m, "emp")
    await client.put(
        f"{CHECK_INS}/{check_in}/note", json={"next_month": "Close in 5 days"}, headers=me
    )
    await run_tick(pg_session_factory, m.org, DEC_2)
    async with pg_session_factory() as db:
        october_rows = {
            r.profile_id: r
            for r in await db.scalars(
                select(AppraisalCheckIn).where(
                    AppraisalCheckIn.org_id == m.org,
                    AppraisalCheckIn.period_start == date(2026, 10, 1),
                )
            )
        }
        november = await db.scalar(
            select(AppraisalCheckIn).where(
                AppraisalCheckIn.org_id == m.org,
                AppraisalCheckIn.period_start == date(2026, 11, 1),
            )
        )
    assert november is not None
    assert all(r.closed_at is not None for r in october_rows.values())
    statuses = sorted(r.status for r in october_rows.values())
    assert statuses == [CheckInStatus.EMPLOYEE_ADDED, CheckInStatus.MISSED]
    late = await client.put(f"{CHECK_INS}/{check_in}/note", json={"blocking": "late"}, headers=me)
    assert late.status_code == 409
