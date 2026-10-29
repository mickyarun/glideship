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

"""A card's checklist: counts on the card, order, caps and other cards' ids."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.services.boards import checklist_service
from tests.integration.board_api_support import BOARDS, card_team, make_card, ok
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration


async def test_the_checklist_counts_on_the_card(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    team = await card_team(client, pg_session_factory)
    url, editor, viewer = team.url, team.editor, team.viewer
    items = [
        ok(await client.post(f"{url}/checklist", json={"text": t}, headers=editor.headers), 201)
        for t in ("One", "Two", "Three")
    ]
    tick = f"{url}/checklist/{items[1]['id']}"
    ok(await client.patch(tick, json={"done": True}, headers=editor.headers))
    card = ok(await client.get(url, headers=viewer.headers))
    assert (card["checklist_done"], card["checklist_total"]) == (1, 3)
    order = [items[2]["id"], items[0]["id"], items[1]["id"]]
    ok(
        await client.put(
            f"{url}/checklist/order", json={"item_ids": order}, headers=editor.headers
        )
    )
    listed = ok(await client.get(f"{url}/checklist", headers=viewer.headers))
    assert [i["text"] for i in listed] == ["Three", "One", "Two"]
    ok(await client.delete(f"{url}/checklist/{items[0]['id']}", headers=editor.headers), 204)
    assert ok(await client.get(url, headers=viewer.headers))["checklist_total"] == 2
    denied = await client.patch(tick, json={"done": False}, headers=viewer.headers)
    assert denied.status_code == 403


async def test_a_checklist_is_capped(
    client: AsyncClient, pg_session_factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    team = await card_team(client, pg_session_factory)
    monkeypatch.setattr(checklist_service, "CHECKLIST_MAX_ITEMS", 2)
    for text in ("a", "b"):
        body = {"text": text}
        ok(await client.post(f"{team.url}/checklist", json=body, headers=team.editor.headers), 201)
    full = await client.post(
        f"{team.url}/checklist", json={"text": "c"}, headers=team.editor.headers
    )
    assert full.status_code == 409


async def test_another_cards_item_is_not_found(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    team = await card_team(client, pg_session_factory)
    other = await make_card(client, team.admin, team.key, "Other")
    other_url = f"{BOARDS}/{team.key}/cards/{other['number']}"
    theirs = ok(
        await client.post(
            f"{other_url}/checklist", json={"text": "x"}, headers=team.admin.headers
        ),
        201,
    )
    item_url = f"{team.url}/checklist/{theirs['id']}"
    edit = await client.patch(item_url, json={"done": True}, headers=team.admin.headers)
    gone = await client.delete(item_url, headers=team.admin.headers)
    assert (edit.status_code, gone.status_code) == (404, 404)
