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

"""The check-in tick's rules: working days, no backfill, refresh, closing, leavers."""

import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.models.appraisal import Appraisal
from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import AppraisalStatus, CheckInStatus, CycleStatus, DraftStatus
from app.models.board import BoardVisibility
from app.models.policy_holiday import HolidayKind, HolidaySource, PolicyHoliday
from app.models.user import OrgToUser, User, UserEmailAlias
from app.services.file_storage import FileStorage
from app.services.leave.policies import ensure_default_policy
from tests.integration.appraisal_month import NOV_2, Month, october, run_tick
from tests.integration.appraisal_support import done_card
from tests.integration.board_support import new_board
from tests.integration.hr_support import configure_hr_storage
from tests.integration.leave_support import Factory, as_user

pytestmark = pytest.mark.integration
EMPLOYEES = "/api/v1/employees"


@pytest.fixture
def hr_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FileStorage:
    """The shared test HR key (see ``hr_support``)."""
    return configure_hr_storage(monkeypatch, tmp_path)


async def _rows(factory: Factory, org: uuid.UUID) -> list[AppraisalCheckIn]:
    async with factory() as db:
        return list(
            await db.scalars(
                select(AppraisalCheckIn)
                .where(AppraisalCheckIn.org_id == org)
                .order_by(AppraisalCheckIn.period_start)
            )
        )


async def _emp_row(factory: Factory, m: Month, start: date) -> AppraisalCheckIn:
    rows = [r for r in await _rows(factory, m.org) if r.period_start == start and r.fact_refs]
    assert len(rows) == 1
    return rows[0]


async def _activated(client: AsyncClient, factory: Factory) -> Month:
    """October set up, but with the first tick undone so each test drives its own."""
    m = await october(client, factory)
    async with factory() as db:
        for row in await db.scalars(
            select(AppraisalCheckIn).where(AppraisalCheckIn.org_id == m.org)
        ):
            await db.delete(row)
        await db.commit()
    return m


async def test_nothing_opens_on_a_weekend_or_a_holiday(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await _activated(client, pg_session_factory)
    await run_tick(pg_session_factory, m.org, datetime(2026, 11, 1, 6, tzinfo=UTC))  # Sunday
    async with pg_session_factory() as db:
        policy = await ensure_default_policy(db, m.org)
        db.add(
            PolicyHoliday(
                org_id=m.org,
                policy_id=policy.id,
                date=date(2026, 11, 2),
                name="Office closed",
                kind=HolidayKind.MANDATORY,
                source=HolidaySource.MANUAL,
            )
        )
        await db.commit()
    await run_tick(pg_session_factory, m.org, NOV_2)
    assert await _rows(pg_session_factory, m.org) == []
    await run_tick(pg_session_factory, m.org, NOV_2 + timedelta(days=1))
    assert len(await _rows(pg_session_factory, m.org)) == 2


async def test_a_late_start_gets_the_latest_month_only(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await _activated(client, pg_session_factory)
    await run_tick(pg_session_factory, m.org, datetime(2026, 12, 1, 6, tzinfo=UTC))
    starts = {r.period_start for r in await _rows(pg_session_factory, m.org)}
    assert starts == {date(2026, 11, 1)}


async def test_open_check_in_refreshes_daily_and_keeps_what_was_written(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    row = await _emp_row(pg_session_factory, m, date(2026, 10, 1))
    me = as_user(m.people["emp"], m.org)
    await client.put(f"/api/v1/check-ins/{row.id}/note", json={"blocking": "Access"}, headers=me)
    board = await new_board(pg_session_factory, m.org, visibility=BoardVisibility.ORG)
    late = await done_card(
        pg_session_factory, board, m.people["emp"], datetime(2026, 10, 30, 9, tzinfo=UTC)
    )
    await run_tick(pg_session_factory, m.org, NOV_2 + timedelta(hours=2))
    assert str(late) not in {
        f["id"] for f in (await _emp_row(pg_session_factory, m, row.period_start)).fact_refs
    }
    await run_tick(pg_session_factory, m.org, NOV_2 + timedelta(hours=21))
    fresh = await _emp_row(pg_session_factory, m, row.period_start)
    assert {f["id"] for f in fresh.fact_refs} == {str(m.counted), str(late)}
    note = (await client.get(f"/api/v1/check-ins/{row.id}", headers=me)).json()["note"]
    assert note["blocking"] == "Access"


async def test_ai_cycle_check_ins_wait_for_a_draft_with_facts_already_saved(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory, ai=True)
    row = await _emp_row(pg_session_factory, m, date(2026, 10, 1))
    assert row.draft_status is DraftStatus.PENDING and row.fact_refs


async def test_closing_a_cycle_early_closes_its_check_ins(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    async with pg_session_factory() as db:
        await db.execute(
            update(AppraisalCycle)
            .where(AppraisalCycle.org_id == m.org)
            .values(status=CycleStatus.CLOSED)
        )
        await db.commit()
    await run_tick(pg_session_factory, m.org, NOV_2 + timedelta(days=1))
    rows = await _rows(pg_session_factory, m.org)
    assert rows and all(r.closed_at is not None for r in rows)
    assert {r.status for r in rows} == {CheckInStatus.MISSED}


async def test_work_left_on_a_merged_account_still_counts(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await _activated(client, pg_session_factory)
    async with pg_session_factory() as db:
        old = User(
            email=f"old-{uuid.uuid4().hex[:6]}@acme.dev",
            name="Priya (old)",
            password_hash="x",
            is_active=False,
        )
        db.add(old)
        await db.flush()
        db.add(OrgToUser(user_id=old.id, org_id=m.org))
        db.add(UserEmailAlias(user_id=m.people["emp"], org_id=m.org, email=old.email))
        await db.commit()
    board = await new_board(pg_session_factory, m.org, visibility=BoardVisibility.ORG)
    merged = await done_card(
        pg_session_factory, board, old.id, datetime(2026, 10, 12, 9, tzinfo=UTC)
    )
    await run_tick(pg_session_factory, m.org, NOV_2)
    row = await _emp_row(pg_session_factory, m, date(2026, 10, 1))
    assert str(merged) in {f["id"] for f in row.fact_refs}


async def test_going_on_notice_withdraws_and_stops_check_ins(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await _activated(client, pg_session_factory)
    hr = as_user(m.people["hr"], m.org)
    record = (await client.get(f"{EMPLOYEES}/{m.people['emp']}", headers=hr)).json()
    moved = await client.put(
        f"{EMPLOYEES}/{m.people['emp']}/work",
        json={**record["work"], "status": "on_notice"},
        headers=hr,
    )
    assert moved.status_code == 200, moved.text
    await run_tick(pg_session_factory, m.org, NOV_2)
    assert len(await _rows(pg_session_factory, m.org)) == 1  # only Meena's
    async with pg_session_factory() as db:
        statuses = set(
            await db.scalars(
                select(Appraisal.status)
                .join(AppraisalCycle, AppraisalCycle.id == Appraisal.cycle_id)
                .where(AppraisalCycle.org_id == m.org)
            )
        )
    assert AppraisalStatus.WITHDRAWN in statuses
