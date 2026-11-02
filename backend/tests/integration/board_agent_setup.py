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

"""Shared setups for the board agent tests: an AI board, and a card with a manual agent."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from httpx import AsyncClient

from app.models.agent_skill import AgentType
from tests.integration.board_agent_support import add_skill, agent, ai_on, set_agents
from tests.integration.board_api_support import (
    BOARDS,
    Person,
    make_board,
    make_card,
    ok,
    person,
    stage_id,
)
from tests.integration.scan_features_bugs_support import Factory, new_org


async def ai_board(
    client: AsyncClient, factory: Factory, *, stage: str = "In progress", ai: bool = True
) -> tuple[uuid.UUID, Person, dict[str, Any], uuid.UUID]:
    org = await new_org(factory)
    admin = await person(factory, org, "pm")
    board = await make_board(client, admin)
    key = board["board"]["key"]
    skill = await add_skill(factory, org)
    await set_agents(client, admin, key, stage_id(board, stage), [agent(skill)])
    await ai_on(client, admin, key, ai)
    return org, admin, board, skill


async def move(client: AsyncClient, who: Person, key: str, number: int, stage: str) -> Any:
    url = f"{BOARDS}/{key}/cards/{number}/move"
    return await client.post(url, json={"stage_id": stage}, headers=who.headers)


@dataclass(frozen=True)
class Setup:
    org: uuid.UUID
    admin: Person
    assignee: Person
    key: str
    board_id: str
    card: dict[str, Any]
    agent_id: str

    @property
    def card_url(self) -> str:
        return f"{BOARDS}/{self.key}/cards/{self.card['number']}"


async def agent_card(
    client: AsyncClient,
    factory: Factory,
    *,
    agent_type: AgentType = AgentType.BOARD_PRD,
    mcp_tools: list[str] | None = None,
) -> Setup:
    org = await new_org(factory)
    admin = await person(factory, org, "org_owner")
    assignee = await person(factory, org)
    board = await make_board(client, admin)
    key, stage = board["board"]["key"], stage_id(board, "To do")
    skill = await add_skill(factory, org, agent_type=agent_type, mcp_tools=mcp_tools)
    (stored,) = await set_agents(client, admin, key, stage, [agent(skill, "manual")])
    await ai_on(client, admin, key)
    ok(
        await client.put(
            f"{BOARDS}/{key}/members/{assignee.id}", json={"role": "editor"}, headers=admin.headers
        )
    )
    made = await make_card(
        client, admin, key, "Refunds page", stage_id=stage, assignee_ids=[str(assignee.id)]
    )
    return Setup(org, admin, assignee, key, board["board"]["id"], made, stored["id"])


async def start(client: AsyncClient, s: Setup) -> dict[str, Any]:
    return dict(
        ok(
            await client.post(f"{s.card_url}/agents/{s.agent_id}/run", headers=s.admin.headers),
            202,
        )
    )


async def docs(client: AsyncClient, s: Setup) -> dict[str, Any]:
    return dict(ok(await client.get(f"{s.card_url}/docs", headers=s.admin.headers)))
