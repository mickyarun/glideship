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


"""A board, its people and their personal MCP tokens, for the board MCP tool tests."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from httpx import AsyncClient, Response

from tests.integration.board_api_support import Person, make_board, make_card, person
from tests.integration.mcp_seed import mint_token
from tests.integration.mcp_support import call
from tests.integration.scan_features_bugs_support import Factory, new_org


@dataclass(frozen=True)
class Tokened:
    """A member, their API headers and their personal MCP token."""

    person: Person
    token: str


@dataclass(frozen=True)
class BoardDesk:
    """An org with a pm (board admin), a developer off the board, a board and one card."""

    org: uuid.UUID
    pm: Tokened
    outsider: Tokened
    board: dict[str, Any]
    card: dict[str, Any]

    @property
    def key(self) -> str:
        """The board's key."""
        return str(self.board["board"]["key"])

    def stage(self, name: str) -> str:
        """The id of the board's stage called ``name``."""
        return next(s["id"] for s in self.board["stages"] if s["name"] == name)


async def tokened(factory: Factory, org: uuid.UUID, role: str = "developer") -> Tokened:
    """A new member holding ``role`` and a personal MCP token."""
    who = await person(factory, org, role)
    token, _ = await mint_token(factory, org, who.id)
    return Tokened(who, token)


async def board_desk(
    client: AsyncClient, factory: Factory, *, visibility: str = "members"
) -> BoardDesk:
    """A fresh org and ops board made by its pm, with one card in Backlog."""
    org = await new_org(factory)
    pm = await tokened(factory, org, "pm")
    outsider = await tokened(factory, org)
    board = await make_board(client, pm.person, visibility=visibility)
    card = await make_card(client, pm.person, board["board"]["key"], "Login page")
    return BoardDesk(org, pm, outsider, board, card)


async def tool(client: AsyncClient, who: Tokened, name: str, **params: Any) -> dict[str, Any]:
    """Call a tool over ``/mcp/tools``; its JSON result (the call itself must be 200)."""
    resp: Response = await call(client, who.token, name, params)
    assert resp.status_code == 200, resp.text
    return dict(resp.json())


def remote_result(resp: Response) -> tuple[bool, dict[str, Any]]:
    """``(isError, tool output)`` from a remote ``tools/call`` envelope."""
    result = resp.json()["result"]
    return result["isError"], json.loads(result["content"][0]["text"])
