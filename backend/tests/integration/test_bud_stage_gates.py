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

"""Stage content gates through the real status PATCH and BUD list.

A BUD can't move to design or later without a PRD, or to development or
later without a tech spec. A refusal leaves the row and timeline as they
were; the list tells the board which sections are written.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.models.bud import BUDStatus
from tests.integration.bud_lifecycle_reads import load_bud, timeline
from tests.integration.bud_lifecycle_support import (
    Factory,
    add_bud,
    add_member,
    as_user,
    new_org,
    stub_externals,
)
from tests.integration.bud_lifecycle_support import (
    app_database_blocked as app_database_blocked,
)

pytestmark = pytest.mark.integration

PRD = "## Problem\nUsers can't export."


async def test_a_bud_without_a_prd_cannot_reach_design(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await add_member(pg_session_factory, org, "pm")
    bud_id = await add_bud(pg_session_factory, org, requirements_md="  ")

    with stub_externals():
        res = await client.patch(
            f"/api/v1/buds/{bud_id}", json={"status": "design"}, headers=as_user(pm, org)
        )

    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "bud_stage_content_missing"
    assert res.json()["detail"]["missing"] == ["prd"]
    assert (await load_bud(pg_session_factory, bud_id)).status is BUDStatus.BUD
    assert await timeline(pg_session_factory, bud_id, "status_change") == []


async def test_a_prd_written_in_the_same_patch_counts(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await add_member(pg_session_factory, org, "pm")
    bud_id = await add_bud(pg_session_factory, org)

    with stub_externals():
        res = await client.patch(
            f"/api/v1/buds/{bud_id}",
            json={"status": "design", "requirements_md": PRD},
            headers=as_user(pm, org),
        )

    assert res.status_code == 200, res.text
    assert (await load_bud(pg_session_factory, bud_id)).status is BUDStatus.DESIGN


async def test_development_needs_the_tech_spec(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await add_member(pg_session_factory, org, "pm")
    bud_id = await add_bud(
        pg_session_factory, org, status=BUDStatus.TECH_ARCH, requirements_md=PRD
    )

    with stub_externals():
        res = await client.patch(
            f"/api/v1/buds/{bud_id}", json={"status": "development"}, headers=as_user(pm, org)
        )

    assert res.status_code == 409
    assert res.json()["detail"]["missing"] == ["tech_spec"]
    assert (await load_bud(pg_session_factory, bud_id)).status is BUDStatus.TECH_ARCH


async def test_closing_stays_open_without_content(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await add_member(pg_session_factory, org, "pm")
    bud_id = await add_bud(pg_session_factory, org)

    with stub_externals():
        res = await client.patch(
            f"/api/v1/buds/{bud_id}", json={"status": "closed"}, headers=as_user(pm, org)
        )

    assert res.status_code == 200, res.text


async def test_the_list_says_which_sections_are_written(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await add_member(pg_session_factory, org, "pm")
    empty = await add_bud(pg_session_factory, org, number=1)
    planned = await add_bud(
        pg_session_factory, org, number=2, requirements_md=PRD, tech_spec_md="## Plan"
    )

    res = await client.get("/api/v1/buds/", headers=as_user(pm, org))

    assert res.status_code == 200, res.text
    by_id = {row["id"]: row for row in res.json()}
    assert (by_id[str(empty)]["has_prd"], by_id[str(empty)]["has_tech_spec"]) == (False, False)
    assert (by_id[str(planned)]["has_prd"], by_id[str(planned)]["has_tech_spec"]) == (True, True)
