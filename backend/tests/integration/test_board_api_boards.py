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

"""Boards through the API: create from a template, list, open, edit, archive."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.services.boards.errors import BOARD_TAKEN
from tests.integration.board_api_support import BOARDS, make_board, ok, person, stage_id
from tests.integration.board_support import board_key
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration


async def test_a_board_starts_from_its_template_with_the_creator_as_admin(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    key = board_key()
    body = await make_board(client, pm, template="product", key=key.lower(), name=" Product ")

    assert body["board"]["key"] == key and body["board"]["name"] == "Product"
    assert [s["name"] for s in body["stages"]] == [
        "Ideas",
        "Shaping",
        "PRD",
        "Ready for dev",
        "Won't do",
    ]
    assert [s["is_default"] for s in body["stages"]] == [True, False, False, False, False]
    assert body["board"]["handover_stage_id"] == stage_id(body, "Ready for dev")
    assert body["board"]["return_stage_id"] == stage_id(body, "Ideas")
    assert body["role"] == "admin" and "manage_members" in body["capabilities"]
    members = ok(await client.get(f"{BOARDS}/{key}/members", headers=pm.headers))
    assert [(m["user_id"], m["role"]) for m in members["members"]] == [(str(pm.id), "admin")]


async def test_templates_are_listed(client: AsyncClient, pg_session_factory: Factory) -> None:
    org = await new_org(pg_session_factory)
    dev = await person(pg_session_factory, org)
    templates = ok(await client.get(f"{BOARDS}/templates", headers=dev.headers))
    assert {"blank", "ops", "product", "design", "content-seo"} <= {t["id"] for t in templates}


@pytest.mark.parametrize(
    "key",
    [
        "A",
        "TOOLONGBOARDKEY",
        "AB1",
        "BUD",
        "bug",
        "TEMPLATES",
        "CARDS",
        "SWITCHER",
        "SKILLS",
        "IMPORTS",
        "LIMITS",
    ],
)
async def test_bad_and_reserved_keys_are_refused(
    client: AsyncClient, pg_session_factory: Factory, key: str
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    body = {"name": "B", "key": key, "template": "blank"}
    assert (await client.post(BOARDS, json=body, headers=pm.headers)).status_code == 422


async def test_creating_needs_boards_create(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    dev = await person(pg_session_factory, org, "developer")
    body = {"name": "B", "key": board_key(), "template": "blank"}
    assert (await client.post(BOARDS, json=body, headers=dev.headers)).status_code == 403


async def test_a_taken_key_or_name_gets_one_message_whoever_can_see_the_board(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    owner, other = [await person(pg_session_factory, org, "pm") for _ in range(2)]
    hidden = (await make_board(client, owner, visibility="members"))["board"]
    shown = (await make_board(client, owner))["board"]

    answers = []
    for taken in (hidden, shown):
        for clash in ({"key": taken["key"]}, {"name": taken["name"].upper()}):
            body = {"name": f"New {board_key()}", "key": board_key(), "template": "blank", **clash}
            resp = await client.post(BOARDS, json=body, headers=other.headers)
            answers.append((resp.status_code, resp.json()))
    assert answers == [(409, {"detail": BOARD_TAKEN})] * 4
    rename = await client.patch(
        f"{BOARDS}/{shown['key']}", json={"name": hidden["name"]}, headers=owner.headers
    )
    assert (rename.status_code, rename.json()) == (409, {"detail": BOARD_TAKEN})


async def test_the_list_shows_my_boards_and_delivery_only_for_engineering(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    sales = await person(pg_session_factory, org, "sales")
    shown = (await make_board(client, pm))["board"]
    hidden = (await make_board(client, pm, visibility="members"))["board"]

    mine = ok(await client.get(BOARDS, headers=pm.headers))["items"]
    assert [i["kind"] for i in mine][-1] == "delivery"
    assert {i["key"] for i in mine if i["kind"] == "custom"} == {shown["key"], hidden["key"]}
    theirs = ok(await client.get(BOARDS, headers=sales.headers))["items"]
    assert theirs == [
        {
            "kind": "custom",
            "id": shown["id"],
            "key": shown["key"],
            "name": shown["name"],
            "visibility": "org",
            "role": "viewer",
            "starred": False,
        }
    ]


async def test_me_says_whether_i_can_open_a_board(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    hr = await person(pg_session_factory, org, "hr")
    me = "/api/v1/auth/me"
    assert ok(await client.get(me, headers=hr.headers))["has_boards"] is False
    pm = await person(pg_session_factory, org, "pm")
    await make_board(client, pm, visibility="members")
    assert ok(await client.get(me, headers=hr.headers))["has_boards"] is False
    await make_board(client, pm)
    assert ok(await client.get(me, headers=hr.headers))["has_boards"] is True


async def test_settings_change_and_handover_rules_hold(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    board = await make_board(client, pm, template="product")
    url = f"{BOARDS}/{board['board']['key']}"
    edits = {"description": "Shaping work", "ai_enabled": True, "handover_enabled": True}
    body = ok(await client.patch(url, json=edits, headers=pm.headers))
    assert body["board"]["description"] == "Shaping work" and body["board"]["ai_enabled"]

    for bad in (
        {"handover_stage_id": stage_id(board, "Ideas")},
        {"return_stage_id": stage_id(board, "PRD")},
        {"handover_target_status": "development"},
        {"handover_stage_id": None},
    ):
        assert (await client.patch(url, json=bad, headers=pm.headers)).status_code == 422, bad
    cleared = {"handover_enabled": False, "handover_stage_id": None, "return_stage_id": None}
    assert (
        ok(await client.patch(url, json=cleared, headers=pm.headers))["board"]["handover_stage_id"]
        is None
    )


async def test_archive_freezes_the_board_until_restored(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    url = f"{BOARDS}/{(await make_board(client, pm))['board']['key']}"
    archived = ok(await client.post(f"{url}/archive", headers=pm.headers))
    assert archived["board"]["status"] == "archived"
    assert archived["capabilities"] == ["view", "archive_board"]
    assert (
        await client.post(f"{url}/cards", json={"title": "x"}, headers=pm.headers)
    ).status_code == 409
    assert ok(await client.get(BOARDS, headers=pm.headers))["items"][:-1] == []
    restored = ok(await client.post(f"{url}/restore", headers=pm.headers))
    assert restored["board"]["status"] == "active"
    ok(await client.post(f"{url}/cards", json={"title": "x"}, headers=pm.headers), 201)
