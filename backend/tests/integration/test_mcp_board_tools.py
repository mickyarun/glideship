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


"""The board MCP tools for a personal token: each one's happy path and its refusals."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.integration.board_api_support import BOARDS, ok, put_role
from tests.integration.board_mcp_support import board_desk, tokened, tool
from tests.integration.mcp_support import (
    Factory,
    mcp_env,  # noqa: F401
)

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("mcp_env")]


async def test_reads_list_the_board_its_stages_and_the_card(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    d = await board_desk(client, pg_session_factory)

    listed = await tool(client, d.pm, "list_boards")
    assert [b["key"] for b in listed["items"] if b["kind"] == "custom"] == [d.key]
    board = await tool(client, d.pm, "get_board", board_key=d.key.lower())
    assert [s["name"] for s in board["stages"]][0] == "Backlog"
    assert board["stages"][0]["cards"][0]["key"] == d.card["key"]
    assert board["role"] == "admin"
    card = await tool(client, d.pm, "get_card", card_key=d.card["key"].lower())
    assert card["card"]["title"] == "Login page" and card["card"]["handovers"] == []
    assert card["board"]["key"] == d.key and card["docs"] == []


async def test_writes_create_edit_move_comment_and_document_a_card(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    d = await board_desk(client, pg_session_factory)
    made = await tool(
        client, d.pm, "create_card", board_key=d.key, title="Billing", stage="in PROGRESS",
        priority="P1",
    )  # fmt: skip
    key = made["card"]["key"]
    assert made["card"]["stage_id"] == d.stage("In progress")

    edited = await tool(client, d.pm, "update_card", card_key=key, title="Billing v2")
    assert edited["card"]["title"] == "Billing v2" and edited["card"]["priority"] == "P1"
    moved = await tool(client, d.pm, "move_card", card_key=key, stage=d.stage("Done"))
    assert moved["card"]["stage_id"] == d.stage("Done")
    said = await tool(client, d.pm, "comment_card", card_key=key, body="Shipped")
    assert said["success"] is True and said["comment"]["body"] == "Shipped"

    doc = {"card_key": key, "kind": "prd"}
    first = await tool(client, d.pm, "write_card_doc", **doc, content_md="v1")
    assert (first["version"], first["state"]) == (1, "current")
    # Once the document exists, leaving base_version out doesn't write over it.
    blind = await tool(client, d.pm, "write_card_doc", **doc, content_md="blind")
    assert (blind["success"], blind["status"]) == (False, 409)
    second = await tool(client, d.pm, "write_card_doc", **doc, content_md="v2", base_version=1)
    assert (second["version"], second["state"]) == (2, "current")
    stale = await tool(client, d.pm, "write_card_doc", **doc, content_md="v3", base_version=1)
    assert (stale["success"], stale["status"]) == (False, 409)
    number = made["card"]["number"]
    docs = ok(
        await client.get(f"{BOARDS}/{d.key}/cards/{number}/docs", headers=d.pm.person.headers)
    )
    assert [(x["kind"], x["body_md"]) for x in docs["items"]] == [("prd", "v2")]


async def test_stage_rules_come_back_with_their_codes(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    d = await board_desk(client, pg_session_factory)
    url = f"{BOARDS}/{d.key}/stages/{d.stage('Waiting')}"
    ok(
        await client.patch(
            url, json={"required_fields": ["assignee"]}, headers=d.pm.person.headers
        )
    )
    card_url = f"{BOARDS}/{d.key}/cards/{d.card['number']}/checklist"
    ok(await client.post(card_url, json={"text": "Test it"}, headers=d.pm.person.headers), 201)
    key = d.card["key"]

    needs = await tool(client, d.pm, "move_card", card_key=key, stage="Waiting")
    assert (needs["status"], needs["code"]) == (422, "STAGE_REQUIREMENTS_MISSING")
    open_items = await tool(client, d.pm, "move_card", card_key=key, stage="Done")
    assert (open_items["status"], open_items["code"]) == (409, "CHECKLIST_OPEN")
    done = await tool(
        client, d.pm, "move_card", card_key=key, stage="Done", confirm_open_checklist=True
    )
    assert done["card"]["stage_id"] == d.stage("Done")
    lost = await tool(client, d.pm, "move_card", card_key=key, stage="Nowhere")
    assert (lost["status"], lost["error"]) == (404, "Stage not found.")
    bad = await tool(client, d.pm, "update_card", card_key=key, priority="urgent")
    assert bad["status"] == 422


async def test_someone_off_a_members_only_board_finds_nothing(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    d = await board_desk(client, pg_session_factory)
    key, card = d.key, d.card["key"]
    calls = [
        ("get_board", {"board_key": key}),
        ("get_card", {"card_key": card}),
        ("create_card", {"board_key": key, "title": "x"}),
        ("update_card", {"card_key": card, "title": "x"}),
        ("move_card", {"card_key": card, "stage": "Done"}),
        ("comment_card", {"card_key": card, "body": "x"}),
        ("write_card_doc", {"card_key": card, "kind": "notes", "content_md": "x"}),
    ]
    for name, params in calls:
        out = await tool(client, d.outsider, name, **params)
        assert (out["success"], out["status"]) == (False, 404), name
        assert out["error"] in {"Board not found.", "Card not found."}
    listed = await tool(client, d.outsider, "list_boards")
    assert [b for b in listed["items"] if b["kind"] == "custom"] == []


async def test_viewers_read_and_comment_but_dont_edit(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    d = await board_desk(client, pg_session_factory)
    await put_role(client, d.pm.person, d.key, d.outsider.person.id, "viewer")
    card = d.card["key"]

    assert (await tool(client, d.outsider, "get_card", card_key=card))["card"]["key"] == card
    assert (await tool(client, d.outsider, "comment_card", card_key=card, body="Hi"))["success"]
    refused = await tool(client, d.outsider, "update_card", card_key=card, title="x")
    assert refused["status"] == 403
    refused = await tool(client, d.outsider, "create_card", board_key=d.key, title="x")
    assert refused["status"] == 403


async def test_an_archived_board_reads_but_refuses_writes(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    d = await board_desk(client, pg_session_factory)
    ok(await client.post(f"{BOARDS}/{d.key}/archive", headers=d.pm.person.headers))
    card = d.card["key"]

    assert (await tool(client, d.pm, "get_board", board_key=d.key))["board"][
        "status"
    ] == "archived"
    assert (await tool(client, d.pm, "get_card", card_key=card))["card"]["key"] == card
    for name, params in [
        ("create_card", {"board_key": d.key, "title": "x"}),
        ("update_card", {"card_key": card, "title": "x"}),
        ("comment_card", {"card_key": card, "body": "x"}),
        ("write_card_doc", {"card_key": card, "kind": "notes", "content_md": "x"}),
    ]:
        assert (await tool(client, d.pm, name, **params))["status"] == 409, name


async def test_another_orgs_board_and_card_are_not_found(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    d = await board_desk(client, pg_session_factory, visibility="org")
    other = await tokened(pg_session_factory, (await board_desk(client, pg_session_factory)).org)

    assert (await tool(client, other, "get_board", board_key=d.key))["status"] == 404
    assert (await tool(client, other, "get_card", card_key=d.card["key"]))["status"] == 404
    out = await tool(client, other, "comment_card", card_key=d.card["key"], body="x")
    assert out["status"] == 404
