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

"""A leave day on a WFH booking stops counting as WFH: allowance and reports."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.models.leave_policy import WfhApproval
from app.models.leave_request import LeaveKind, LeaveStatus
from app.repositories.leave_request import LeaveRequestRepository
from app.schemas.leave import LeaveRequestCreate
from app.services.leave.evaluation import evaluate
from app.services.leave.policies import ensure_default_policy, resolve_member_policy
from app.services.leave.slack_context import prompt_context
from app.services.leave.wfh_usage import wfh_days_by_month
from tests.integration.leave_support import (
    Factory,
    add_request,
    as_user,
    month_mondays,
    report_to,
    setup_org,
    team,
)
from tests.integration.period_support import add_period_leave

pytestmark = pytest.mark.integration
SUMMARY = "/api/v1/leave/reports/summary"
JUNE = {"start": "2026-06-01", "end": "2026-06-30"}
MON, THU, FRI = date(2026, 6, 1), date(2026, 6, 4), date(2026, 6, 5)


async def _auto_approved(factory: Factory, org: uuid.UUID, emp: uuid.UUID, day: date) -> bool:
    body = LeaveRequestCreate(kind=LeaveKind.WFH, start_date=day, end_date=day)
    async with factory() as db:
        member = await resolve_member_policy(db, org, emp)
        return (await evaluate(db, member=member, user_id=emp, body=body)).auto_approved


async def _wfh_days(client: AsyncClient, viewer: uuid.UUID, org: uuid.UUID) -> Decimal:
    report = await client.get(SUMMARY, params=JUNE, headers=as_user(viewer, org))
    assert report.status_code == 200
    return Decimal(next(r for r in report.json()["rows"] if r["name"] == "Emp")["wfh_days"])


async def test_only_approved_leave_gives_a_wfh_day_back_to_the_allowance(
    pg_session_factory: Factory,
) -> None:
    org, (emp, mgr), casual = await setup_org(pg_session_factory, "Emp", "Mgr")
    await report_to(pg_session_factory, org, emp, mgr)
    async with pg_session_factory() as db:
        policy = (await resolve_member_policy(db, org, emp)).policy
        policy.wfh_approval, policy.wfh_monthly_auto_days = WfhApproval.AUTO_WITHIN_ALLOWANCE, 2
        await db.commit()
    mon = month_mondays()[0]
    tue, wed = mon + timedelta(days=1), mon + timedelta(days=2)
    await add_request(pg_session_factory, org, emp, mon, tue, "2", kind=LeaveKind.WFH)
    assert not await _auto_approved(pg_session_factory, org, emp, wed)
    await add_request(
        pg_session_factory, org, emp, tue, tue, "1", type_id=casual, status=LeaveStatus.PENDING
    )
    assert not await _auto_approved(pg_session_factory, org, emp, wed)
    await add_request(pg_session_factory, org, emp, mon, mon, "1", type_id=casual)
    assert await _auto_approved(pg_session_factory, org, emp, wed)


async def test_the_summary_counts_a_week_once(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, p, casual = await team(pg_session_factory)
    emp = p["emp"]
    await add_request(pg_session_factory, org, emp, MON, FRI, "5", kind=LeaveKind.WFH)
    await add_request(pg_session_factory, org, emp, THU, THU, "1", type_id=casual)
    assert await _wfh_days(client, p["hr"], org) == 4
    report = await client.get(SUMMARY, params=JUNE, headers=as_user(p["hr"], org))
    row = next(r for r in report.json()["rows"] if r["name"] == "Emp")
    assert Decimal(row["leave_days"]) == 1


async def test_the_summary_only_takes_back_days_inside_the_range(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, p, casual = await team(pg_session_factory)
    emp = p["emp"]
    # Mon 29 Jun - Fri 3 Jul: two WFH days in June, one of them on leave.
    start, end = date(2026, 6, 29), date(2026, 7, 3)
    await add_request(pg_session_factory, org, emp, start, end, "5", kind=LeaveKind.WFH)
    await add_request(
        pg_session_factory, org, emp, date(2026, 6, 30), date(2026, 7, 1), "2", type_id=casual
    )
    assert await _wfh_days(client, p["hr"], org) == 1


async def test_a_hidden_leave_type_does_not_show_up_in_wfh_days(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, p, _ = await team(pg_session_factory)
    emp = p["emp"]
    period = await add_period_leave(pg_session_factory, org, emp)
    await add_request(pg_session_factory, org, emp, MON, FRI, "5", kind=LeaveKind.WFH)
    await add_request(pg_session_factory, org, emp, THU, THU, "1", type_id=period)
    # A manager can't see this type, so the day stays WFH for them.
    assert await _wfh_days(client, p["mgr"], org) == 5


async def test_wfh_days_never_go_below_zero_when_the_calendar_has_changed(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, p, casual = await team(pg_session_factory)
    emp = p["emp"]
    # Booked as 4 days around a holiday that has since been removed.
    await add_request(pg_session_factory, org, emp, MON, FRI, "4", kind=LeaveKind.WFH)
    await add_request(pg_session_factory, org, emp, MON, FRI, "4", type_id=casual)
    assert await _wfh_days(client, p["hr"], org) == 0


async def test_the_approvers_dm_does_not_give_away_a_hidden_leave_type(
    pg_session_factory: Factory,
) -> None:
    org, p, casual = await team(pg_session_factory)
    period = await add_period_leave(pg_session_factory, org, p["emp"])
    for person, leave_type in ((p["emp"], period), (p["peer"], casual)):
        await add_request(pg_session_factory, org, person, MON, FRI, "5", kind=LeaveKind.WFH)
        await add_request(pg_session_factory, org, person, THU, THU, "1", type_id=leave_type)

    async def usage_line(person: uuid.UUID) -> str:
        async with pg_session_factory() as db:
            [wfh] = await LeaveRequestRepository(db, org_id=org).active_between(
                [person], MON, FRI, kinds=[LeaveKind.WFH]
            )
            return (await prompt_context(db, org, wfh))[0]

    assert (await usage_line(p["emp"])).startswith("With this, 5 WFH days in Jun")
    assert (await usage_line(p["peer"])).startswith("With this, 4 WFH days in Jun")
    # Their own allowance still gets the day back.
    async with pg_session_factory() as db:
        policy = await ensure_default_policy(db, org)
        own = await wfh_days_by_month(db, policy, p["emp"], MON, FRI)
    assert own[(2026, 6)] == 4
