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

"""A card can't enter a Done stage with open checklist items unless the move confirms it."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from tests.integration.board_api_support import BOARDS, Person, make_card, ok, stage_id
from tests.integration.board_move_support import card_url, move, require, rules_board, supply
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration


async def _checklist(
    client: AsyncClient, who: Person, board: dict[str, Any], card: dict[str, Any], done: list[bool]
) -> None:
    url = f"{card_url(board, card)}/checklist"
    for flag in done:
        item = ok(await client.post(url, json={"text": "step"}, headers=who.headers), 201)
        if flag:
            ok(await client.patch(f"{url}/{item['id']}", json={"done": True}, headers=who.headers))


async def test_done_refuses_open_checklist_items_unless_confirmed(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    _, editor, board = await rules_board(client, pg_session_factory)
    card = await make_card(client, editor, board["board"]["key"])
    await _checklist(client, editor, board, card, [True, False, False])
    ok(await move(client, editor, board, card, "In progress"))
    refused = await move(client, editor, board, card, "Done")
    assert refused.status_code == 409
    assert refused.json() == {
        "detail": "2 of 3 checklist items are still open.",
        "code": "CHECKLIST_OPEN",
        "open": 2,
        "total": 3,
    }
    moved = ok(await move(client, editor, board, card, "Done", confirm_open_checklist=True))
    assert moved["stage_id"] == stage_id(board, "Done")
    # Already in Done: reordering there and restoring it check nothing.
    ok(await client.post(f"{card_url(board, card)}/archive", headers=editor.headers))
    ok(await client.post(f"{card_url(board, card)}/restore", headers=editor.headers))


async def test_done_takes_cards_with_no_checklist_or_a_finished_one(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    admin, editor, board = await rules_board(client, pg_session_factory)
    key = board["board"]["key"]
    bare, finished = await make_card(client, editor, key), await make_card(client, editor, key)
    await _checklist(client, editor, board, finished, [True, True])
    ok(await move(client, editor, board, bare, "Done"))
    ok(await move(client, editor, board, finished, "Done"))
    done = stage_id(board, "Done")
    created = ok(
        await client.post(
            f"{BOARDS}/{key}/cards",
            json={"title": "Shipped", "stage_id": done, "confirm_open_checklist": True},
            headers=editor.headers,
        ),
        201,
    )
    assert created["stage_id"] == done


async def test_required_fields_are_checked_before_the_checklist(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    admin, editor, board = await rules_board(client, pg_session_factory)
    ok(await require(client, admin, board, "Done", ["assignee"]))
    card = await make_card(client, editor, board["board"]["key"])
    await _checklist(client, editor, board, card, [False])
    refused = await move(client, editor, board, card, "Done", confirm_open_checklist=True)
    assert refused.status_code == 422 and refused.json()["missing"] == ["assignee"]
    await supply(client, editor, board, card, "assignee")
    assert (await move(client, editor, board, card, "Done")).status_code == 409
