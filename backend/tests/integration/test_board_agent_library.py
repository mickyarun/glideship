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

"""The board skills are seeded into every org, and the stage picker lists the whole library."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.models.agent_skill import AgentType
from app.services.skill_loader import seed_skills_for_org
from tests.integration.board_agent_support import add_skill
from tests.integration.board_api_support import BOARDS, make_board, ok, person, put_role
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration


async def test_the_stage_picker_lists_the_library_with_the_board_skills_first(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    async with pg_session_factory() as db:
        await seed_skills_for_org(org, db)
        await db.commit()
    custom = await add_skill(pg_session_factory, org, agent_type=AgentType.TRIAGE, name="Aaa")
    admin = await person(pg_session_factory, org, "org_owner")
    board = await make_board(client, admin)
    key = board["board"]["key"]

    listed = ok(await client.get(f"{BOARDS}/{key}/skills", headers=admin.headers))

    first, second = listed[:2]
    assert (first["slug"], first["agent_type"], first["suggested"], first["output_kind"]) == (
        "board-prd-writer",
        "boardPrd",
        True,
        "prd",
    )
    assert (second["slug"], second["suggested"], second["output_kind"]) == (
        "board-design-helper",
        True,
        "design_brief",
    )
    rest = listed[2:]
    assert not any(s["suggested"] for s in rest)
    mine = next(s for s in rest if s["id"] == str(custom))
    assert mine["output_kind"] == "notes"
    assert {s["agent_type"] for s in rest} >= {"bud", "design", "techPlan"}
    assert {"id", "name", "slug", "agent_type", "suggested", "output_kind"} == set(first)


async def test_only_board_admins_see_the_library(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    admin = await person(pg_session_factory, org, "org_owner")
    editor = await person(pg_session_factory, org)
    board = await make_board(client, admin)
    key = board["board"]["key"]
    await put_role(client, admin, key, editor.id, "editor")
    resp = await client.get(f"{BOARDS}/{key}/skills", headers=editor.headers)
    assert resp.status_code == 403
