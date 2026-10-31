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

"""Helpers for the stage entry-rule tests: an ops board, requirements, moves."""

from __future__ import annotations

from typing import Any

from httpx import AsyncClient

from tests.integration.board_api_support import (
    BOARDS,
    Person,
    make_board,
    ok,
    person,
    put_role,
    stage_id,
)
from tests.integration.scan_features_bugs_support import Factory, new_org

FIELDS = ("assignee", "due_date", "priority", "label", "description", "prd")


async def rules_board(
    client: AsyncClient, factory: Factory
) -> tuple[Person, Person, dict[str, Any]]:
    """An ops board in a new org, its admin, and an editor on it."""
    org = await new_org(factory)
    admin, editor = await person(factory, org, "pm"), await person(factory, org)
    board = await make_board(client, admin)
    await put_role(client, admin, board["board"]["key"], editor.id, "editor")
    return admin, editor, board


async def require(
    client: AsyncClient, admin: Person, board: dict[str, Any], stage: str, fields: list[str]
) -> Any:
    """PATCH the stage's required fields; the raw response."""
    url = f"{BOARDS}/{board['board']['key']}/stages/{stage_id(board, stage)}"
    return await client.patch(url, json={"required_fields": fields}, headers=admin.headers)


def card_url(board: dict[str, Any], card: dict[str, Any]) -> str:
    """The card's API url."""
    return f"{BOARDS}/{board['board']['key']}/cards/{card['number']}"


async def move(
    client: AsyncClient,
    who: Person,
    board: dict[str, Any],
    card: dict[str, Any],
    stage: str,
    **extra: Any,
) -> Any:
    """Move the card to the bottom of ``stage``; the raw response."""
    body = {"stage_id": stage_id(board, stage), **extra}
    return await client.post(f"{card_url(board, card)}/move", json=body, headers=who.headers)


async def supply(
    client: AsyncClient, who: Person, board: dict[str, Any], card: dict[str, Any], field: str
) -> None:
    """Give the card what ``field`` requires."""
    url, key = card_url(board, card), board["board"]["key"]
    if field == "prd":
        body = {"body_md": "What and why", "base_version": None}
        ok(await client.put(f"{url}/docs/prd", json=body, headers=who.headers))
        return
    if field == "label":
        label = ok(
            await client.post(
                f"{BOARDS}/{key}/labels", json={"name": "L", "color": "red"}, headers=who.headers
            ),
            201,
        )
        patch: dict[str, Any] = {"label_ids": [label["id"]]}
    else:
        patch = {
            "assignee": {"assignee_ids": [str(who.id)]},
            "due_date": {"due_at": "2030-01-01T00:00:00Z"},
            "priority": {"priority": "P1"},
            "description": {"description_md": "Context"},
        }[field]
    ok(await client.patch(url, json=patch, headers=who.headers))
