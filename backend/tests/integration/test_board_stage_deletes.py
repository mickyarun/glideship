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

"""Deleting and re-categorising stages: protected stages, targets, archived cards, stamps."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.integration.board_api_support import (
    BOARDS,
    make_board,
    make_card,
    ok,
    page,
    person,
    stage_id,
)
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration


async def test_the_return_stage_cant_be_deleted(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    board = await make_board(client, pm, template="product")
    url = f"{BOARDS}/{board['board']['key']}/stages"
    # Ideas is the return stage and the default; make another the default first.
    shaping = stage_id(board, "Shaping")
    ok(await client.patch(f"{url}/{shaping}", json={"is_default": True}, headers=pm.headers))
    resp = await client.delete(f"{url}/{stage_id(board, 'Ideas')}", headers=pm.headers)
    assert resp.status_code == 409


async def test_cards_can_only_move_to_another_stage_of_this_board(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    board = await make_board(client, pm, template="ops")
    other = await make_board(client, pm, template="ops")
    waiting = stage_id(board, "Waiting")
    url = f"{BOARDS}/{board['board']['key']}/stages/{waiting}"
    for target in (waiting, stage_id(other, "Done")):
        resp = await client.delete(url, params={"move_to": target}, headers=pm.headers)
        assert resp.status_code == 404, target


async def test_a_stage_with_only_archived_cards_still_needs_a_target(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    board = await make_board(client, pm, template="ops")
    key = board["board"]["key"]
    waiting, done = stage_id(board, "Waiting"), stage_id(board, "Done")
    card = await make_card(client, pm, key, "Parked", stage_id=waiting)
    ok(await client.post(f"{BOARDS}/{key}/cards/{card['number']}/archive", headers=pm.headers))
    url = f"{BOARDS}/{key}/stages/{waiting}"
    assert (await client.delete(url, headers=pm.headers)).status_code == 422
    ok(await client.delete(url, params={"move_to": done}, headers=pm.headers), 204)
    shelf = await page(client, pm, key, done, archived="true")
    assert [c["title"] for c in shelf["items"]] == ["Parked"]


async def test_recategorising_a_stage_restamps_its_cards(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    board = await make_board(client, pm, template="ops")
    key = board["board"]["key"]
    waiting = stage_id(board, "Waiting")
    card = await make_card(client, pm, key, "Waiting on legal", stage_id=waiting)
    assert card["started_at"] is not None and card["completed_at"] is None
    url = f"{BOARDS}/{key}/stages/{waiting}"
    card_url = f"{BOARDS}/{key}/cards/{card['number']}"

    ok(await client.patch(url, json={"category": "done"}, headers=pm.headers))
    done = ok(await client.get(card_url, headers=pm.headers))
    assert done["completed_at"] is not None and done["started_at"] == card["started_at"]
    ok(await client.patch(url, json={"category": "todo"}, headers=pm.headers))
    reopened = ok(await client.get(card_url, headers=pm.headers))
    assert reopened["completed_at"] is None and reopened["started_at"] == card["started_at"]
