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

"""The stage jobs a status PATCH starts, and ``create_bud`` with a ready embedding."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.models.bud import BUDDocument, BUDStatus
from app.schemas.bud import BUDCreate
from app.services.bud_create import create_bud, embed_text_for
from app.services.bud_stage_jobs import run_stage_jobs
from app.services.embedding_service import embedding_service
from tests.integration.bud_lifecycle_support import (
    EMBEDDING_DIM,
    Factory,
    add_bud,
    add_member,
    as_user,
    bud_in_testing,
    new_org,
    stub_externals,
)
from tests.integration.bud_lifecycle_support import (
    app_database_blocked as app_database_blocked,
)

pytestmark = pytest.mark.integration


async def _patch(
    client: AsyncClient, org: uuid.UUID, pm: uuid.UUID, bud: uuid.UUID, to: str
) -> None:
    res = await client.patch(f"/api/v1/buds/{bud}", json={"status": to}, headers=as_user(pm, org))
    assert res.status_code == 200, res.text


async def test_testing_to_uat_with_the_phase_off_skips_the_estimate(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """The phase switch stops the stage work, and the re-estimate with it."""
    org, bud_id = await bud_in_testing(pg_session_factory, "pass")
    pm = await add_member(pg_session_factory, org, "pm")
    with stub_externals() as ext:
        await _patch(client, org, pm, bud_id, "uat")
    ext.bg_estimate.assert_not_called()


async def test_uat_to_uat_re_estimates(client: AsyncClient, pg_session_factory: Factory) -> None:
    """No stage change runs no agent, but the UAT re-estimate still goes out."""
    org = await new_org(pg_session_factory)
    bud_id = await add_bud(pg_session_factory, org, status=BUDStatus.UAT)
    pm = await add_member(pg_session_factory, org, "pm")
    with stub_externals() as ext:
        await _patch(client, org, pm, bud_id, "uat")
    ext.bg_estimate.assert_called_once()


async def test_code_review_without_an_open_pr_asks_for_no_agent(
    pg_session_factory: Factory,
) -> None:
    """Phase on, no open PR: the review agent waits for the PR webhook."""
    org = await new_org(pg_session_factory)
    bud_id = await add_bud(
        pg_session_factory,
        org,
        status=BUDStatus.DEVELOPMENT,
        auto_generate_phases={"code_review": True},
    )
    pm = await add_member(pg_session_factory, org, "pm")
    spawn = AsyncMock(return_value=None)
    async with pg_session_factory() as db:
        bud = await db.get(BUDDocument, bud_id)
        assert bud is not None
        with patch("app.services.bud_stage_jobs.create_agent_task_for_stage", spawn):
            outcome = await run_stage_jobs(
                db, org, bud, BUDStatus.DEVELOPMENT, BUDStatus.CODE_REVIEW, triggered_by=pm
            )
    assert outcome.stopped is True
    spawn.assert_not_awaited()


async def test_create_bud_keeps_a_given_embedding(pg_session_factory: Factory) -> None:
    """A precomputed vector is stored as it is; the BUD's text isn't embedded again."""
    org = await new_org(pg_session_factory)
    pm = await add_member(pg_session_factory, org, "pm")
    vector = [0.25] * EMBEDDING_DIM
    # The planned feature embeds its own text; only the BUD's must not be.
    embed = AsyncMock(return_value=[0.0] * EMBEDDING_DIM)
    async with pg_session_factory() as db:
        with patch.object(embedding_service, "embed", embed):
            bud = await create_bud(
                db,
                org_id=org,
                body=BUDCreate(title="Plans table"),
                actor_id=pm,
                actor_name="PM",
                embedding=vector,
                start_stage=False,
            )
        await db.commit()
        bud_id = bud.id
    async with pg_session_factory() as db:
        stored = await db.get(BUDDocument, bud_id)
        assert stored is not None and stored.embedding is not None
        assert [round(float(x), 4) for x in stored.embedding] == vector
    assert embed_text_for("Plans table", None) not in [c.args[0] for c in embed.await_args_list]
