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

"""An approver sees everything the requester has taken this year, retired types too."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.models.leave_request import LeaveStatus
from app.models.leave_type import LeaveType
from app.services.leave.policies import ensure_default_policy
from tests.integration.leave_support import (
    Factory,
    add_request,
    as_user,
    future_monday,
    report_to,
    setup_org,
)

pytestmark = pytest.mark.integration
D = Decimal


async def test_card_totals_every_type_and_lists_a_retired_one_with_days(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, (emp, mgr), casual = await setup_org(pg_session_factory, "Emp", "Mgr")
    await report_to(pg_session_factory, org, emp, mgr)
    async with pg_session_factory() as db:
        policy = await ensure_default_policy(db, org)
        retired = LeaveType(
            org_id=org, policy_id=policy.id, name="Vacation", code="VA", is_active=False
        )
        unused_retired = LeaveType(
            org_id=org, policy_id=policy.id, name="Old sick", code="OS", is_active=False
        )
        db.add_all([retired, unused_retired])
        await db.commit()
        retired_id = retired.id
    mon = future_monday()
    year_start = mon.replace(month=1, day=5)
    await add_request(
        pg_session_factory,
        org,
        emp,
        year_start,
        year_start + timedelta(days=1),
        "2",
        type_id=casual,
    )
    later = year_start + timedelta(weeks=2)
    await add_request(
        pg_session_factory, org, emp, later, later + timedelta(days=3), "4", type_id=retired_id
    )
    # Pending doesn't count toward the total taken.
    await add_request(
        pg_session_factory,
        org,
        emp,
        mon,
        mon,
        "1",
        type_id=casual,
        status=LeaveStatus.PENDING,
    )

    [card] = (await client.get("/api/v1/leave/approvals", headers=as_user(mgr, org))).json()[
        "items"
    ]
    assert D(card["taken_this_year"]) == D(6)
    names = {b["leave_type"]["name"] for b in card["balances"]}
    assert "Vacation" in names
    assert "Old sick" not in names
