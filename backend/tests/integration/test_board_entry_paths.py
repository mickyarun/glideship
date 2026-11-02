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

"""Entry rules through the API: blank text, completed stages, archived cards, defaults."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from tests.integration.board_api_support import BOARDS, Person, make_card, ok, stage_id
from tests.integration.board_move_support import card_url, move, require, rules_board
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration

NBSP = "    "


async def _stage(
    client: AsyncClient,
    admin: Person,
    board: dict[str, Any],
    name: str,
    category: str,
    **extra: Any,
) -> dict[str, Any]:
    url = f"{BOARDS}/{board['board']['key']}/stages"
    body = {"name": name, "category": category, **extra}
    created = ok(await client.post(url, json=body, headers=admin.headers), 201)
    board["stages"].append(created)
    return dict(created)


async def _open_item(client: AsyncClient, who: Person, board: dict[str, Any], card: Any) -> None:
    url = f"{card_url(board, card)}/checklist"
    ok(await client.post(url, json={"text": "step"}, headers=who.headers), 201)


async def test_unicode_blank_description_is_no_description_on_create_and_move(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    admin, editor, board = await rules_board(client, pg_session_factory)
    key = board["board"]["key"]
    ok(await require(client, admin, board, "Waiting", ["description"]))
    body = {"title": "x", "stage_id": stage_id(board, "Waiting"), "description_md": NBSP}
    created = await client.post(f"{BOARDS}/{key}/cards", json=body, headers=editor.headers)
    card = await make_card(client, editor, key, description_md=NBSP)
    moved = await move(client, editor, board, card, "Waiting")
    assert (created.status_code, moved.status_code) == (422, 422)
    assert created.json()["missing"] == moved.json()["missing"] == ["description"]
    assert (card["description_md"], card["has_description"]) == (None, False)
    patched = ok(
        await client.patch(
            card_url(board, card), json={"description_md": NBSP}, headers=editor.headers
        )
    )
    assert patched["description_md"] is None


async def test_a_required_field_can_be_cleared_after_the_card_entered(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    admin, editor, board = await rules_board(client, pg_session_factory)
    ok(await require(client, admin, board, "Waiting", ["due_date"]))
    card = await make_card(client, editor, board["board"]["key"], due_at="2030-01-01T00:00:00Z")
    ok(await move(client, editor, board, card, "Waiting"))
    cleared = ok(
        await client.patch(card_url(board, card), json={"due_at": None}, headers=editor.headers)
    )
    assert cleared["due_at"] is None and cleared["stage_id"] == stage_id(board, "Waiting")


async def test_done_to_done_and_canceled_stages_skip_the_checklist(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    admin, editor, board = await rules_board(client, pg_session_factory)
    await _stage(client, admin, board, "Dropped", "canceled")
    await _stage(client, admin, board, "Shipped", "done")
    card = await make_card(client, editor, board["board"]["key"])
    await _open_item(client, editor, board, card)
    ok(await move(client, editor, board, card, "Dropped"))
    # From canceled, the card is already complete; Done to Done too.
    ok(await move(client, editor, board, card, "Done"))
    ok(await move(client, editor, board, card, "Shipped"))
    ok(await move(client, editor, board, card, "In progress"))
    refused = await move(client, editor, board, card, "Shipped")
    assert refused.status_code == 409
    assert refused.json()["detail"] == "1 of 1 checklist items is still open."


async def test_an_archived_card_or_board_is_409_before_any_rule(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    admin, editor, board = await rules_board(client, pg_session_factory)
    key = board["board"]["key"]
    ok(await require(client, admin, board, "Waiting", ["assignee"]))
    card = await make_card(client, editor, key)
    other = await make_card(client, editor, key, "Other")
    ok(await client.post(f"{card_url(board, card)}/archive", headers=editor.headers))
    assert (await move(client, editor, board, card, "Waiting")).status_code == 409
    ok(await client.post(f"{BOARDS}/{key}/archive", headers=admin.headers))
    assert (await move(client, editor, board, other, "Waiting")).status_code == 409


async def test_a_new_stage_stores_its_required_fields_in_declaration_order(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    admin, _, board = await rules_board(client, pg_session_factory)
    fields = ["prd", "label", "assignee"]
    stage = await _stage(client, admin, board, "Review", "in_progress", required_fields=fields)
    assert stage["required_fields"] == ["assignee", "label", "prd"]


async def test_the_default_stage_cant_require_a_prd(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    admin, _, board = await rules_board(client, pg_session_factory)
    url = f"{BOARDS}/{board['board']['key']}/stages"
    refused = await require(client, admin, board, "Backlog", ["prd"])
    assert refused.status_code == 422 and "no PRD" in refused.json()["detail"]
    ok(await require(client, admin, board, "Waiting", ["prd"]))
    waiting = f"{url}/{stage_id(board, 'Waiting')}"
    made_default = await client.patch(waiting, json={"is_default": True}, headers=admin.headers)
    assert made_default.status_code == 422
    body = {"name": "Intake", "category": "todo", "is_default": True, "required_fields": ["prd"]}
    assert (await client.post(url, json=body, headers=admin.headers)).status_code == 422
    detail = ok(await client.get(f"{BOARDS}/{board['board']['key']}", headers=admin.headers))
    assert next(s for s in detail["stages"] if s["is_default"])["name"] == "Backlog"
