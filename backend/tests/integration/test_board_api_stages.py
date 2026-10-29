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

"""Stages and labels: the rules every board keeps, and moving cards off a deleted stage."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.config import settings
from app.models.board_card_detail import BoardCardEvent
from tests.integration.board_api_support import (
    BOARDS,
    Person,
    make_board,
    make_card,
    ok,
    page,
    person,
    stage_id,
)
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration


async def _board(client: AsyncClient, factory: Factory) -> tuple[Person, dict[str, Any]]:
    org = await new_org(factory)
    pm = await person(factory, org, "pm")
    return pm, await make_board(client, pm, template="blank")


async def test_stages_can_be_added_edited_and_reordered(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    pm, board = await _board(client, pg_session_factory)
    url = f"{BOARDS}/{board['board']['key']}/stages"
    review = ok(
        await client.post(
            url,
            json={"name": "Review", "category": "in_progress", "wip_limit": 3},
            headers=pm.headers,
        ),
        201,
    )
    assert review["position"] == 3 and review["wip_limit"] == 3
    edited = ok(
        await client.patch(
            f"{url}/{review['id']}",
            json={"name": "QA", "wip_limit": None, "is_default": True},
            headers=pm.headers,
        )
    )
    assert (edited["name"], edited["wip_limit"], edited["is_default"]) == ("QA", None, True)
    detail = ok(await client.get(f"{BOARDS}/{board['board']['key']}", headers=pm.headers))
    assert [s["name"] for s in detail["stages"] if s["is_default"]] == ["QA"]

    order = [review["id"], *[s["id"] for s in board["stages"]]]
    reordered = ok(await client.put(f"{url}/order", json={"stage_ids": order}, headers=pm.headers))
    assert [s["id"] for s in reordered] == order and [s["position"] for s in reordered] == [
        0,
        1,
        2,
        3,
    ]
    partial = await client.put(f"{url}/order", json={"stage_ids": order[:2]}, headers=pm.headers)
    assert partial.status_code == 422


async def test_stage_rules_are_kept(client: AsyncClient, pg_session_factory: Factory) -> None:
    pm, board = await _board(client, pg_session_factory)
    key = board["board"]["key"]
    url = f"{BOARDS}/{key}/stages"
    todo, done = stage_id(board, "To do"), stage_id(board, "Done")
    # The only done stage can't become something else, nor be deleted.
    resp = await client.patch(f"{url}/{done}", json={"category": "todo"}, headers=pm.headers)
    assert resp.status_code == 422
    assert (await client.delete(f"{url}/{done}", headers=pm.headers)).status_code == 422
    # The default can't be unset or deleted; it moves by naming another.
    resp = await client.patch(f"{url}/{todo}", json={"is_default": False}, headers=pm.headers)
    assert resp.status_code == 422
    assert (await client.delete(f"{url}/{todo}", headers=pm.headers)).status_code == 422
    # Names are unique per board.
    taken = await client.post(url, json={"name": "Done", "category": "done"}, headers=pm.headers)
    assert taken.status_code == 409
    # And there's a cap.
    room = settings.boards.max_stages_per_board - len(board["stages"])
    for i in range(room):
        body = {"name": f"Extra {i}", "category": "in_progress"}
        ok(await client.post(url, json=body, headers=pm.headers), 201)
    over = await client.post(
        url, json={"name": "One more", "category": "todo"}, headers=pm.headers
    )
    assert over.status_code == 422


async def test_the_handover_stage_cant_be_deleted(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    board = await make_board(client, pm, template="product")
    url = f"{BOARDS}/{board['board']['key']}/stages/{stage_id(board, 'Ready for dev')}"
    assert (await client.delete(url, headers=pm.headers)).status_code == 409


async def test_deleting_a_stage_moves_its_cards_first(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    pm, board = await _board(client, pg_session_factory)
    key = board["board"]["key"]
    doing, done = stage_id(board, "In progress"), stage_id(board, "Done")
    finished = await make_card(client, pm, key, "Finished", stage_id=done)
    moving = [await make_card(client, pm, key, f"Card {i}", stage_id=doing) for i in range(3)]
    url = f"{BOARDS}/{key}/stages/{doing}"
    assert (await client.delete(url, headers=pm.headers)).status_code == 422
    ok(await client.delete(url, params={"move_to": done}, headers=pm.headers), 204)

    cards = (await page(client, pm, key, done))["items"]
    assert [c["title"] for c in cards] == ["Finished", "Card 0", "Card 1", "Card 2"]
    detail = ok(
        await client.get(f"{BOARDS}/{key}/cards/{moving[0]['number']}", headers=pm.headers)
    )
    assert detail["completed_at"] is not None and detail["started_at"] is not None
    assert finished["completed_at"] is not None
    async with pg_session_factory() as db:
        events = (
            await db.scalars(
                select(BoardCardEvent).where(
                    BoardCardEvent.card_id == moving[0]["id"], BoardCardEvent.type == "moved"
                )
            )
        ).all()
    assert [(e.from_category, e.to_category, e.from_stage_id) for e in events] == [
        ("in_progress", "done", None)
    ]


async def test_labels_are_unique_per_board(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    pm, board = await _board(client, pg_session_factory)
    url = f"{BOARDS}/{board['board']['key']}/labels"
    label = ok(
        await client.post(url, json={"name": "Bug", "color": "red"}, headers=pm.headers), 201
    )
    assert (
        await client.post(url, json={"name": "Bug", "color": "blue"}, headers=pm.headers)
    ).status_code == 409
    bad = await client.post(url, json={"name": "Pink", "color": "#ff00ff"}, headers=pm.headers)
    assert bad.status_code == 422
    edited = ok(
        await client.patch(f"{url}/{label['id']}", json={"color": "green"}, headers=pm.headers)
    )
    assert edited == {"id": label["id"], "name": "Bug", "color": "green"}
    other = await make_board(client, pm, template="blank")
    same_name = await client.post(
        f"{BOARDS}/{other['board']['key']}/labels",
        json={"name": "Bug", "color": "red"},
        headers=pm.headers,
    )
    assert same_name.status_code == 201
    ok(await client.delete(f"{url}/{label['id']}", headers=pm.headers), 204)
    assert ok(await client.get(url, headers=pm.headers)) == []
