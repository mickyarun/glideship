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

"""Required fields per stage, checked on moves and creates into that stage."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.integration.board_api_support import BOARDS, make_card, ok, stage_id
from tests.integration.board_move_support import (
    FIELDS,
    card_url,
    move,
    require,
    rules_board,
    supply,
)
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration


async def test_admins_set_required_fields_once_each_and_in_order(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    admin, editor, board = await rules_board(client, pg_session_factory)
    stage = ok(await require(client, admin, board, "Waiting", ["prd", "assignee"]))
    assert stage["required_fields"] == ["assignee", "prd"]
    assert (await require(client, editor, board, "Waiting", ["label"])).status_code == 403
    assert (await require(client, admin, board, "Waiting", ["label", "label"])).status_code == 422
    assert (await require(client, admin, board, "Waiting", ["colour"])).status_code == 422
    detail = ok(await client.get(f"{BOARDS}/{board['board']['key']}", headers=editor.headers))
    by_name = {s["name"]: s["required_fields"] for s in detail["stages"]}
    assert by_name["Waiting"] == ["assignee", "prd"] and by_name["Backlog"] == []
    cleared = ok(await require(client, admin, board, "Waiting", []))
    assert cleared["required_fields"] == []


@pytest.mark.parametrize("field", FIELDS)
async def test_a_move_needs_each_required_field(
    client: AsyncClient, pg_session_factory: Factory, field: str
) -> None:
    admin, editor, board = await rules_board(client, pg_session_factory)
    ok(await require(client, admin, board, "In progress", [field]))
    card = await make_card(client, editor, board["board"]["key"])
    refused = await move(client, editor, board, card, "In progress")
    assert refused.status_code == 422
    assert refused.json() == {
        "detail": refused.json()["detail"],
        "code": "STAGE_REQUIREMENTS_MISSING",
        "stage_id": stage_id(board, "In progress"),
        "missing": [field],
    }
    # The admin, who may also add the label.
    await supply(client, admin, board, card, field)
    moved = ok(await move(client, editor, board, card, "In progress"))
    assert moved["stage_id"] == stage_id(board, "In progress")


async def test_a_refusal_lists_every_missing_field_and_blank_text_is_missing(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    admin, editor, board = await rules_board(client, pg_session_factory)
    ok(await require(client, admin, board, "In progress", list(reversed(FIELDS))))
    card = await make_card(client, editor, board["board"]["key"], description_md="  \n ")
    url = card_url(board, card)
    ok(
        await client.put(
            f"{url}/docs/prd", json={"body_md": " ", "base_version": None}, headers=editor.headers
        )
    )
    refused = await move(client, editor, board, card, "In progress")
    assert refused.status_code == 422
    assert refused.json()["missing"] == list(FIELDS)
    assert "an assignee" in refused.json()["detail"] and "a PRD" in refused.json()["detail"]
    summary = ok(await client.get(url, headers=editor.headers))
    assert (summary["has_description"], summary["has_prd"]) == (False, False)


async def test_reordering_inside_a_stage_and_restoring_skip_the_rules(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    admin, editor, board = await rules_board(client, pg_session_factory)
    first = await make_card(client, editor, board["board"]["key"], "First")
    second = await make_card(client, editor, board["board"]["key"], "Second")
    ok(await require(client, admin, board, "Backlog", ["assignee"]))
    ok(await move(client, editor, board, second, "Backlog", before_id=first["id"]))
    ok(await client.post(f"{card_url(board, first)}/archive", headers=editor.headers))
    ok(await client.post(f"{card_url(board, first)}/restore", headers=editor.headers))


async def test_a_create_into_a_stage_needs_its_fields(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    admin, editor, board = await rules_board(client, pg_session_factory)
    key, waiting = board["board"]["key"], stage_id(board, "Waiting")
    ok(await require(client, admin, board, "Waiting", ["assignee", "due_date", "description"]))
    url = f"{BOARDS}/{key}/cards"
    refused = await client.post(
        url, json={"title": "x", "stage_id": waiting}, headers=editor.headers
    )
    assert refused.status_code == 422
    assert refused.json()["code"] == "STAGE_REQUIREMENTS_MISSING"
    assert refused.json()["missing"] == ["assignee", "due_date", "description"]
    body = {
        "title": "x",
        "stage_id": waiting,
        "assignee_ids": [str(editor.id)],
        "due_at": "2030-01-01T00:00:00Z",
        "description_md": "Context",
    }
    ok(await client.post(url, json=body, headers=editor.headers), 201)
    ok(await require(client, admin, board, "Waiting", ["prd"]))
    no_prd = await client.post(url, json=body, headers=editor.headers)
    assert no_prd.json()["missing"] == ["prd"]
    # The default stage's rules apply when no stage is named.
    ok(await require(client, admin, board, "Backlog", ["priority"]))
    plain = await client.post(url, json={"title": "y"}, headers=editor.headers)
    assert plain.json()["missing"] == ["priority"]


async def test_moving_a_deleted_stages_cards_skips_the_rules(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    admin, editor, board = await rules_board(client, pg_session_factory)
    card = await make_card(client, editor, board["board"]["key"])
    ok(await move(client, editor, board, card, "Waiting"))
    ok(await require(client, admin, board, "In progress", list(FIELDS)))
    url = f"{BOARDS}/{board['board']['key']}/stages/{stage_id(board, 'Waiting')}"
    target = stage_id(board, "In progress")
    ok(await client.delete(url, params={"move_to": target}, headers=admin.headers), 204)
    moved = ok(await client.get(card_url(board, card), headers=editor.headers))
    assert moved["stage_id"] == target
