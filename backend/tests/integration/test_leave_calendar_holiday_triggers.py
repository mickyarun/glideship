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

"""Changing holidays or moving people re-syncs calendars, once the change is saved."""

from __future__ import annotations

import uuid
from collections.abc import Coroutine
from datetime import date
from typing import Any

import pytest
from httpx import AsyncClient

from app.api.v1 import employee_updates, employees, leave_holidays, leave_policies
from app.schemas.leave_policy import PolicyWrite
from tests.integration.leave_edge_support import add_holiday, add_policy
from tests.integration.leave_support import Factory, as_user, give_role, setup_org

pytestmark = pytest.mark.integration
LEAVE = "/api/v1/leave"


@pytest.fixture
def started(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    """The background jobs the handlers start: (function name, its arguments)."""
    jobs: list[tuple[str, dict[str, Any]]] = []

    def spawn(job: Coroutine[Any, Any, None]) -> None:
        jobs.append((job.cr_code.co_name, dict(job.cr_frame.f_locals)))
        job.close()

    for module in (leave_holidays, leave_policies, employees, employee_updates):
        monkeypatch.setattr(module, "spawn", spawn)
    return jobs


async def _hr_org(factory: Factory) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    org, (hr, emp), _ = await setup_org(factory, "Hr", "Emp")
    await give_role(factory, org, hr, "hr")
    policy, _ = await add_policy(factory, org, "Chennai")
    return org, hr, emp, policy


async def test_adding_editing_and_deleting_a_holiday_resyncs_that_policy(
    client: AsyncClient, pg_session_factory: Factory, started: list[tuple[str, dict[str, Any]]]
) -> None:
    org, hr, _emp, policy = await _hr_org(pg_session_factory)
    added = await client.post(
        f"{LEAVE}/policies/{policy}/holidays",
        json={"date": "2030-06-19", "name": "Fest"},
        headers=as_user(hr, org),
    )
    assert added.status_code == 201, added.text
    holiday = added.json()["id"]
    moved = await client.put(
        f"{LEAVE}/holidays/{holiday}",
        json={"date": "2030-06-17", "name": "Fest"},
        headers=as_user(hr, org),
    )
    assert moved.status_code == 200, moved.text
    gone = await client.delete(f"{LEAVE}/holidays/{holiday}", headers=as_user(hr, org))
    assert gone.status_code == 204, gone.text
    assert [(name, str(args["policy_id"]), str(args["start"])) for name, args in started] == [
        ("after_holiday_change", str(policy), "2030-06-19"),
        ("after_holiday_change", str(policy), "2030-06-17"),
        ("after_holiday_change", str(policy), "2030-06-17"),
    ]


async def test_a_refused_change_starts_nothing(
    client: AsyncClient, pg_session_factory: Factory, started: list[tuple[str, dict[str, Any]]]
) -> None:
    org, hr, _emp, policy = await _hr_org(pg_session_factory)
    await add_holiday(pg_session_factory, org, policy, date(2030, 6, 19), "Fest")
    clash = await client.post(
        f"{LEAVE}/policies/{policy}/holidays",
        json={"date": "2030-06-19", "name": "Again"},
        headers=as_user(hr, org),
    )
    assert clash.status_code == 409, clash.text
    assert started == []


async def test_moving_people_onto_a_policy_resyncs_their_holidays(
    client: AsyncClient, pg_session_factory: Factory, started: list[tuple[str, dict[str, Any]]]
) -> None:
    org, hr, emp, policy = await _hr_org(pg_session_factory)
    moved = await client.post(
        f"{LEAVE}/policies/{policy}/assign",
        json={"user_ids": [str(emp)]},
        headers=as_user(hr, org),
    )
    assert moved.status_code == 200, moved.text
    assert [(name, args["user_ids"]) for name, args in started] == [("sync_holidays", [emp])]


async def test_a_new_timezone_or_default_resyncs_holidays_but_a_rename_does_not(
    client: AsyncClient, pg_session_factory: Factory, started: list[tuple[str, dict[str, Any]]]
) -> None:
    org, hr, _emp, policy = await _hr_org(pg_session_factory)
    current = await client.get(f"{LEAVE}/policies", headers=as_user(hr, org))
    body = next(p for p in current.json() if p["id"] == str(policy))
    write = {k: body[k] for k in PolicyWrite.model_fields if k in body}
    renamed = await client.put(
        f"{LEAVE}/policies/{policy}", json={**write, "name": "Chennai office"},
        headers=as_user(hr, org),
    )  # fmt: skip
    assert renamed.status_code == 200, renamed.text
    assert started == []
    moved = await client.put(
        f"{LEAVE}/policies/{policy}",
        json={**write, "name": "Chennai office", "timezone": "Asia/Kolkata"},
        headers=as_user(hr, org),
    )
    assert moved.status_code == 200, moved.text
    made = await client.post(f"{LEAVE}/policies/{policy}/default", headers=as_user(hr, org))
    assert made.status_code == 200, made.text
    assert [(name, args["policy_id"]) for name, args in started] == [
        ("sync_holidays", policy),
        ("sync_holidays", None),
    ]
