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

"""Who else is out, in the approvals queue, when a teammate has WFH and leave."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from app.models.leave_request import LeaveKind, LeaveStatus
from tests.integration.leave_support import (
    Factory,
    add_request,
    as_user,
    future_monday,
    report_to,
    setup_org,
)

pytestmark = pytest.mark.integration
QUEUE = "/api/v1/leave/approvals"


async def _team(factory: Factory) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    org, (emp, mate, mgr), casual = await setup_org(factory, "Emp", "Mate", "Mgr")
    await report_to(factory, org, emp, mgr)
    await report_to(factory, org, mate, mgr)
    return org, emp, mate, mgr, casual


async def _kinds(
    client: AsyncClient, factory: Factory, org: uuid.UUID, emp: uuid.UUID, mgr: uuid.UUID,
    casual: uuid.UUID, start: date, end: date,
) -> list[str]:  # fmt: skip
    """What the manager sees for a teammate, on Emp's request for ``start..end``."""
    days = str((end - start).days + 1)
    await add_request(
        factory, org, emp, start, end, days, type_id=casual, status=LeaveStatus.PENDING
    )
    page = await client.get(QUEUE, headers=as_user(mgr, org))
    assert page.status_code == 200, page.text
    mine = next(i for i in page.json()["items"] if i["request"]["user"]["name"] == "Emp")
    return sorted(out["kind"] for out in mine["also_out"])


async def test_wfh_that_leave_replaces_is_not_listed(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, emp, mate, mgr, casual = await _team(pg_session_factory)
    mon = future_monday()
    wed = mon + timedelta(2)
    await add_request(
        pg_session_factory, org, mate, mon, mon + timedelta(4), "5", kind=LeaveKind.WFH
    )
    await add_request(pg_session_factory, org, mate, wed, wed, "1", type_id=casual)
    assert await _kinds(client, pg_session_factory, org, emp, mgr, casual, wed, wed) == ["leave"]


async def test_wfh_stays_for_a_day_they_are_working(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, emp, mate, mgr, casual = await _team(pg_session_factory)
    mon = future_monday()
    tue, wed = mon + timedelta(1), mon + timedelta(2)
    await add_request(
        pg_session_factory, org, mate, mon, mon + timedelta(4), "5", kind=LeaveKind.WFH
    )
    await add_request(pg_session_factory, org, mate, wed, wed, "1", type_id=casual)
    kinds = await _kinds(client, pg_session_factory, org, emp, mgr, casual, tue, wed)
    assert kinds == ["leave", "wfh"]


async def test_pending_leave_replaces_nothing(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, emp, mate, mgr, casual = await _team(pg_session_factory)
    mon = future_monday()
    await add_request(pg_session_factory, org, mate, mon, mon, "1", kind=LeaveKind.WFH)
    await add_request(
        pg_session_factory, org, mate, mon, mon, "1", type_id=casual, status=LeaveStatus.PENDING
    )
    kinds = await _kinds(client, pg_session_factory, org, emp, mgr, casual, mon, mon)
    assert kinds == ["leave", "wfh"]


async def test_a_weekend_inside_the_wfh_does_not_keep_it_listed(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, emp, mate, mgr, casual = await _team(pg_session_factory)
    fri = future_monday() + timedelta(4)
    next_mon = fri + timedelta(3)
    await add_request(pg_session_factory, org, mate, fri, next_mon, "2", kind=LeaveKind.WFH)
    await add_request(pg_session_factory, org, mate, fri, fri, "1", type_id=casual)
    await add_request(pg_session_factory, org, mate, next_mon, next_mon, "1", type_id=casual)
    kinds = await _kinds(client, pg_session_factory, org, emp, mgr, casual, fri, next_mon)
    assert kinds == ["leave", "leave"]
