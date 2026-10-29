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

"""Helpers for the boards API tests: people, boards and cards made through HTTP."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from httpx import AsyncClient

from tests.integration.board_support import board_key
from tests.integration.scan_features_bugs_support import Factory, as_user, new_member

BOARDS = "/api/v1/boards"


@dataclass(frozen=True)
class Person:
    """A member and the headers that sign them in."""

    id: uuid.UUID
    headers: dict[str, str]


async def person(factory: Factory, org: uuid.UUID, role: str | None = "developer") -> Person:
    """A new member of ``org`` holding the system role ``role``."""
    user = await new_member(factory, org, role)
    return Person(user, as_user(user, org))


def ok(resp: Any, code: int = 200) -> Any:
    """The JSON body, after checking the status."""
    assert resp.status_code == code, resp.text
    return resp.json() if resp.content else None


async def make_board(
    client: AsyncClient, who: Person, *, template: str = "ops", **body: Any
) -> dict[str, Any]:
    """A board made through the API by ``who`` (who becomes its admin)."""
    payload = {"name": f"Board {uuid.uuid4().hex[:6]}", "key": board_key(), "template": template}
    return ok(await client.post(BOARDS, json={**payload, **body}, headers=who.headers), 201)


def stage_id(board: dict[str, Any], name: str) -> str:
    """The id of the board's stage called ``name``."""
    return next(s["id"] for s in board["stages"] if s["name"] == name)


async def make_card(
    client: AsyncClient, who: Person, key: str, title: str = "Card", **body: Any
) -> dict[str, Any]:
    """A card made through the API."""
    url = f"{BOARDS}/{key}/cards"
    return ok(await client.post(url, json={"title": title, **body}, headers=who.headers), 201)


async def put_role(
    client: AsyncClient, admin: Person, key: str, user: uuid.UUID, role: str
) -> dict[str, Any]:
    """Give ``user`` their own role on the board."""
    url = f"{BOARDS}/{key}/members/{user}"
    return ok(await client.put(url, json={"role": role}, headers=admin.headers))


async def page(
    client: AsyncClient, who: Person, key: str, stage: str, **params: Any
) -> dict[str, Any]:
    """One page of a stage's cards."""
    url = f"{BOARDS}/{key}/cards"
    return ok(await client.get(url, params={"stage_id": stage, **params}, headers=who.headers))
