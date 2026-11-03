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

"""The holiday list over HTTP: a whole leave year, own office by default.

Everyone reads their own office's calendar; only people who run leave
may switch to another office's.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.models.employee_profile import EmployeeProfile
from app.models.policy_holiday import HolidayKind
from tests.integration.leave_edge_support import add_holiday, add_policy, freeze_today
from tests.integration.leave_support import (
    Factory,
    add_member_without_profile,
    as_user,
    give_role,
    setup_org,
)

pytestmark = pytest.mark.integration
HOLIDAYS = "/api/v1/leave/holidays"
TODAY = date(2030, 6, 3)


@pytest.fixture(autouse=True)
def _frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    freeze_today(monkeypatch, TODAY)


async def _move(factory: Factory, user: uuid.UUID, policy: uuid.UUID) -> None:
    async with factory() as db:
        await db.execute(
            update(EmployeeProfile)
            .where(EmployeeProfile.user_id == user)
            .values(leave_policy_id=policy)
        )
        await db.commit()


async def _two_offices(factory: Factory) -> tuple[uuid.UUID, dict[str, uuid.UUID]]:
    """Ravi in Chennai (April leave year), Amy on the default; Hr runs leave."""
    org, (hr, ravi, amy), _ = await setup_org(factory, "Hr", "Ravi", "Amy")
    await give_role(factory, org, hr, "hr")
    chennai, _ = await add_policy(factory, org, "Chennai", year_start_month=4)
    await _move(factory, ravi, chennai)
    await add_holiday(factory, org, chennai, date(2030, 1, 14), "Pongal")  # last leave year
    await add_holiday(factory, org, chennai, date(2030, 4, 14), "Tamil New Year")
    await add_holiday(factory, org, chennai, date(2030, 11, 1), "Diwali", HolidayKind.OPTIONAL)
    await add_holiday(factory, org, chennai, date(2031, 1, 14), "Pongal")
    return org, {"hr": hr, "ravi": ravi, "amy": amy, "chennai": chennai}


async def _get(
    client: AsyncClient, org: uuid.UUID, viewer: uuid.UUID, **params: str
) -> dict[str, Any]:
    response = await client.get(HOLIDAYS, params=params, headers=as_user(viewer, org))
    assert response.status_code == 200, response.text
    return dict(response.json())


async def test_a_member_sees_their_office_for_the_current_leave_year(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, p = await _two_offices(pg_session_factory)
    body = await _get(client, org, p["ravi"])
    assert body["calendar"]["name"] == "Chennai"
    assert [c["name"] for c in body["calendars"]] == ["Chennai"]
    assert body["leave_year"] == {"label": 2030, "start": "2030-04-01", "end": "2031-03-31"}
    assert body["today"] == TODAY.isoformat()
    assert [(h["date"], h["name"], h["kind"]) for h in body["holidays"]] == [
        ("2030-04-14", "Tamil New Year", "mandatory"),
        ("2030-11-01", "Diwali", "optional"),
        ("2031-01-14", "Pongal", "mandatory"),
    ]


async def test_the_year_switches_by_leave_year_label(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, p = await _two_offices(pg_session_factory)
    body = await _get(client, org, p["ravi"], year="2029")
    assert body["leave_year"]["start"] == "2029-04-01"
    assert [h["date"] for h in body["holidays"]] == ["2030-01-14"]


async def test_a_member_cannot_read_another_offices_calendar(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, p = await _two_offices(pg_session_factory)
    response = await client.get(
        HOLIDAYS, params={"policy_id": str(p["chennai"])}, headers=as_user(p["amy"], org)
    )
    assert response.status_code == 403, response.text
    own = await _get(client, org, p["amy"])
    assert own["calendar"]["name"] == "Default" and own["holidays"] == []


async def test_hr_can_switch_between_every_office(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, p = await _two_offices(pg_session_factory)
    own = await _get(client, org, p["hr"])
    assert own["calendar"]["name"] == "Default"
    assert [c["name"] for c in own["calendars"]] == ["Default", "Chennai"]
    chennai = await _get(client, org, p["hr"], policy_id=str(p["chennai"]))
    assert chennai["calendar"]["id"] == str(p["chennai"])
    assert len(chennai["holidays"]) == 3


async def test_another_orgs_calendar_is_not_found_even_for_hr(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, p = await _two_offices(pg_session_factory)
    other, (stranger,), _ = await setup_org(pg_session_factory, "Stranger")
    await give_role(pg_session_factory, other, stranger, "hr")
    response = await client.get(
        HOLIDAYS, params={"policy_id": str(p["chennai"])}, headers=as_user(stranger, other)
    )
    assert response.status_code == 404, response.text


async def test_someone_without_an_employee_record_gets_the_default_calendar(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, p = await _two_offices(pg_session_factory)
    newcomer = await add_member_without_profile(pg_session_factory, org, "Newcomer")
    body = await _get(client, org, newcomer)
    assert body["calendar"]["name"] == "Default"
    assert [c["name"] for c in body["calendars"]] == ["Default"]
