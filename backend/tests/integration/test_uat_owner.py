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

"""The org's UAT owner through the real routes.

When an org makes QA the UAT owner, a QA user (buds:test, no buds:edit)
may move a BUD from UAT to prod or back to development, and nothing else.
With the default PM owner those moves stay refused. Any BUD viewer can
read the stage settings, including QA, who can't read the full settings.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.models.bud import BUDStatus
from tests.integration.bud_lifecycle_reads import load_bud
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

QA_OWNS_UAT = {"bud_stages": {"uat_enabled": True, "uat_owner": "qa"}}


async def _qa_moves(
    client: AsyncClient, factory: Factory, config: dict[str, object], target: BUDStatus
) -> tuple[int, BUDStatus]:
    org = await new_org(factory, config)
    qa = await add_member(factory, org, "qa", role="qa")
    bud_id = await add_bud(factory, org, status=BUDStatus.UAT)
    with stub_externals():
        res = await client.patch(
            f"/api/v1/buds/{bud_id}", json={"status": target.value}, headers=as_user(qa, org)
        )
    return res.status_code, (await load_bud(factory, bud_id)).status


@pytest.mark.parametrize("target", [BUDStatus.PROD, BUDStatus.DEVELOPMENT])
async def test_qa_owner_moves_a_bud_out_of_uat(
    client: AsyncClient, pg_session_factory: Factory, target: BUDStatus
) -> None:
    assert await _qa_moves(client, pg_session_factory, QA_OWNS_UAT, target) == (200, target)


@pytest.mark.parametrize("target", [BUDStatus.PROD, BUDStatus.DEVELOPMENT])
async def test_qa_cannot_move_out_of_uat_when_pm_owns_it(
    client: AsyncClient, pg_session_factory: Factory, target: BUDStatus
) -> None:
    assert await _qa_moves(client, pg_session_factory, {}, target) == (403, BUDStatus.UAT)


async def test_qa_owner_gets_no_other_uat_moves(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    moved = await _qa_moves(client, pg_session_factory, QA_OWNS_UAT, BUDStatus.TESTING)
    assert moved == (403, BUDStatus.UAT)


async def test_qa_reads_their_own_orgs_stage_settings(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory, QA_OWNS_UAT)
    other = await new_org(pg_session_factory)
    qa = await add_member(pg_session_factory, org, "qa", role="qa")
    other_pm = await add_member(pg_session_factory, other, "pm")

    mine = await client.get("/api/v1/settings/bud-stages", headers=as_user(qa, org))
    theirs = await client.get("/api/v1/settings/bud-stages", headers=as_user(other_pm, other))

    assert (mine.status_code, mine.json()) == (200, {"uatEnabled": True, "uatOwner": "qa"})
    assert (theirs.status_code, theirs.json()) == (200, {"uatEnabled": True, "uatOwner": "pm"})


async def test_stage_settings_need_bud_access(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory, QA_OWNS_UAT)
    support = await add_member(pg_session_factory, org, "support", role="support")

    res = await client.get("/api/v1/settings/bud-stages", headers=as_user(support, org))

    assert res.status_code == 403


async def test_saving_stage_settings_without_an_owner_keeps_the_stored_one(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """An older client that doesn't send uatOwner must not reset it to the PM."""
    org = await new_org(pg_session_factory, QA_OWNS_UAT)
    admin = await add_member(pg_session_factory, org, "owner", role="org_owner")
    headers = as_user(admin, org)

    saved = await client.patch(
        "/api/v1/settings/connections", json={"budStages": {"uatEnabled": True}}, headers=headers
    )
    read = await client.get("/api/v1/settings/bud-stages", headers=headers)

    assert saved.status_code == 200
    assert read.json() == {"uatEnabled": True, "uatOwner": "qa"}

    switched = await client.patch(
        "/api/v1/settings/connections", json={"budStages": {"uatOwner": "pm"}}, headers=headers
    )
    assert switched.status_code == 200
    assert (await client.get("/api/v1/settings/bud-stages", headers=headers)).json() == {
        "uatEnabled": True,
        "uatOwner": "pm",
    }
