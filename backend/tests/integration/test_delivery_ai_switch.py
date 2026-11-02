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

"""Delivery's AI switch: its settings route, and BUD stage agents starting only while it's on."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.bud import BUDDocument, BUDStatus
from app.models.bud_agent_task import BUDAgentTask
from app.services.bud_agent_trigger import create_agent_task_for_stage
from app.services.bud_stage_seeder import seed_stage_mappings_for_org
from app.services.delivery_settings import DELIVERY_AI_OFF
from app.services.skill_loader import seed_skills_for_org
from tests.integration.board_api_support import ok, person
from tests.integration.bud_lifecycle_support import add_bud
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration

URL = "/api/v1/settings/delivery"


async def _org_with_agents(factory: Factory) -> tuple[uuid.UUID, uuid.UUID]:
    org = await new_org(factory)
    async with factory() as db:
        await seed_skills_for_org(org, db)
        await seed_stage_mappings_for_org(org, db)
        await db.commit()
    return org, await add_bud(factory, org)


async def _start_prd_agent(factory: Factory, org: uuid.UUID, bud_id: uuid.UUID) -> Any:
    job = MagicMock(job_id=str(uuid.uuid4()))
    async with factory() as db:
        bud = await db.get(BUDDocument, bud_id)
        assert bud is not None
        with patch("app.services.job_queue.create_job", return_value=job) as create:
            task = await create_agent_task_for_stage(bud, "bud", org, db, force=True)
        tasks = await db.scalar(
            select(func.count()).select_from(BUDAgentTask).where(BUDAgentTask.bud_id == bud_id)
        )
    return task, create.call_count, tasks


async def test_delivery_ai_is_on_by_default_and_only_settings_editors_change_it(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    owner = await person(pg_session_factory, org, "org_owner")
    dev = await person(pg_session_factory, org)
    assert ok(await client.get(URL, headers=dev.headers)) == {"ai_enabled": True}
    refused = await client.patch(URL, json={"ai_enabled": False}, headers=dev.headers)
    assert refused.status_code == 403
    assert ok(await client.patch(URL, json={"ai_enabled": False}, headers=owner.headers)) == {
        "ai_enabled": False
    }
    assert ok(await client.get(URL, headers=dev.headers)) == {"ai_enabled": False}
    bad = await client.patch(URL, json={"ai": False}, headers=owner.headers)
    assert bad.status_code == 422


async def test_with_delivery_ai_off_no_bud_stage_agent_starts(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, bud_id = await _org_with_agents(pg_session_factory)
    owner = await person(pg_session_factory, org, "org_owner")
    ok(await client.patch(URL, json={"ai_enabled": False}, headers=owner.headers))
    task, jobs, tasks = await _start_prd_agent(pg_session_factory, org, bud_id)
    assert (task, jobs, tasks) == (None, 0, 0)


async def test_with_delivery_ai_on_the_stage_agent_starts_as_before(
    pg_session_factory: Factory,
) -> None:
    org, bud_id = await _org_with_agents(pg_session_factory)
    task, jobs, tasks = await _start_prd_agent(pg_session_factory, org, bud_id)
    assert task is not None and (jobs, tasks) == (1, 1)


async def test_with_delivery_ai_off_regenerating_learnings_says_the_switch_is_off(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, _bud = await _org_with_agents(pg_session_factory)
    owner = await person(pg_session_factory, org, "org_owner")
    closed = await add_bud(
        pg_session_factory,
        org,
        number=2,
        status=BUDStatus.CLOSED,
        auto_generate_phases={"closed": True},
    )
    ok(await client.patch(URL, json={"ai_enabled": False}, headers=owner.headers))
    url = f"/api/v1/buds/{closed}/learning/regenerate"
    refused = await client.post(url, headers=owner.headers)
    assert (refused.status_code, refused.json()["detail"]) == (409, DELIVERY_AI_OFF)
