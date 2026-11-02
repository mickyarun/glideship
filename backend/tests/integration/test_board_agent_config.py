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

"""Setting up a stage's agents: admins only, any skill from the org's own library.

The card's AI panel shows what Run offers on the card's stage to anyone who
can see the card.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.models.agent_skill import AgentType
from tests.integration.board_agent_support import add_skill, agent, ai_on
from tests.integration.board_api_support import (
    BOARDS,
    make_board,
    make_card,
    ok,
    person,
    put_role,
    stage_id,
)
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration


async def test_admins_replace_a_stages_agents_and_editors_cannot(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    admin = await person(pg_session_factory, org, "pm")
    editor = await person(pg_session_factory, org)
    board = await make_board(client, admin)
    key, stage = board["board"]["key"], stage_id(board, "To do")
    await put_role(client, admin, key, editor.id, "editor")
    prd = await add_skill(pg_session_factory, org)
    custom = await add_skill(pg_session_factory, org, agent_type=AgentType.SKILL, name="Mine")
    url = f"{BOARDS}/{key}/stages/{stage}/agents"
    body = [agent(custom, "manual", order=2), agent(prd, "on_enter", order=1)]
    assert (await client.put(url, json=body, headers=editor.headers)).status_code == 403
    assert (await client.get(url, headers=editor.headers)).status_code == 403
    stored = ok(await client.put(url, json=body, headers=admin.headers))
    assert [(a["skill_id"], a["trigger"], a["order"], a["output_kind"]) for a in stored] == [
        (str(prd), "on_enter", 1, "prd"),
        (str(custom), "manual", 2, "notes"),
    ]
    assert ok(await client.get(url, headers=admin.headers)) == stored
    # Replacing again swaps the list (orders may be reused).
    again = ok(await client.put(url, json=[agent(custom, "manual")], headers=admin.headers))
    assert [a["skill_id"] for a in again] == [str(custom)]


async def test_a_skill_from_another_org_is_refused(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, elsewhere = await new_org(pg_session_factory), await new_org(pg_session_factory)
    admin = await person(pg_session_factory, org, "pm")
    board = await make_board(client, admin)
    foreign = await add_skill(pg_session_factory, elsewhere)
    url = f"{BOARDS}/{board['board']['key']}/stages/{stage_id(board, 'To do')}/agents"
    resp = await client.put(url, json=[agent(foreign)], headers=admin.headers)
    assert resp.status_code == 422
    assert resp.json()["code"] == "SKILL_NOT_IN_LIBRARY"
    assert resp.json()["skill_ids"] == [str(foreign)]


async def test_two_on_enter_agents_or_a_repeated_order_are_refused(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    admin = await person(pg_session_factory, org, "pm")
    board = await make_board(client, admin)
    one, two = await add_skill(pg_session_factory, org), await add_skill(pg_session_factory, org)
    url = f"{BOARDS}/{board['board']['key']}/stages/{stage_id(board, 'To do')}/agents"
    twice = [agent(one, order=1), agent(two, order=2)]
    assert (await client.put(url, json=twice, headers=admin.headers)).status_code == 422
    same_order = [agent(one, "manual", order=1), agent(two, "manual", order=1)]
    assert (await client.put(url, json=same_order, headers=admin.headers)).status_code == 422
    elsewhere = f"{BOARDS}/{board['board']['key']}/stages/{org}/agents"
    assert (await client.put(elsewhere, json=[], headers=admin.headers)).status_code == 404


async def test_the_card_panel_lists_its_stages_switched_on_agents(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    admin = await person(pg_session_factory, org, "pm")
    viewer = await person(pg_session_factory, org)
    board = await make_board(client, admin, visibility="members")
    key, stage = board["board"]["key"], stage_id(board, "To do")
    await put_role(client, admin, key, viewer.id, "viewer")
    on, off = await add_skill(pg_session_factory, org), await add_skill(pg_session_factory, org)
    url = f"{BOARDS}/{key}/stages/{stage}/agents"
    agents = [agent(on, "manual", order=1), agent(off, "manual", order=2, enabled=False)]
    ok(await client.put(url, json=agents, headers=admin.headers))
    made = await make_card(client, admin, key, stage_id=stage)
    panel_url = f"{BOARDS}/{key}/cards/{made['number']}/agents"
    panel = ok(await client.get(panel_url, headers=viewer.headers))
    assert panel["ai_enabled"] is False
    assert [a["skill_id"] for a in panel["agents"]] == [str(on)]
    assert (panel["runs"], panel["active"]) == ([], None)
    await ai_on(client, admin, key)
    assert ok(await client.get(panel_url, headers=viewer.headers))["ai_enabled"] is True
    outsider = await person(pg_session_factory, org)
    assert (await client.get(panel_url, headers=outsider.headers)).status_code == 404
