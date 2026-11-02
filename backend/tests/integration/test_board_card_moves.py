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

"""Moving cards: midpoints, rebalancing, concurrent moves, timestamps and history."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.config import settings
from app.models.board_card import BoardCard
from app.models.board_card_detail import BoardCardEvent
from app.services import event_bus
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


async def _setup(client: AsyncClient, factory: Factory) -> tuple[Person, dict[str, Any], str]:
    org = await new_org(factory)
    pm = await person(factory, org, "pm")
    board = await make_board(client, pm, template="ops")
    return pm, board, board["board"]["key"]


async def _move(
    client: AsyncClient, who: Person, key: str, number: int, **body: Any
) -> dict[str, Any]:
    url = f"{BOARDS}/{key}/cards/{number}/move"
    return ok(await client.post(url, json=body, headers=who.headers))


async def _titles(client: AsyncClient, who: Person, key: str, stage: str) -> list[str]:
    return [c["title"] for c in (await page(client, who, key, stage))["items"]]


async def _events(factory: Factory, card_id: str) -> list[BoardCardEvent]:
    async with factory() as db:
        rows = await db.scalars(
            select(BoardCardEvent)
            .where(BoardCardEvent.card_id == uuid.UUID(card_id))
            .order_by(BoardCardEvent.created_at, BoardCardEvent.id)
        )
        return list(rows)


async def test_a_card_lands_between_its_neighbours(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    pm, board, key = await _setup(client, pg_session_factory)
    todo = stage_id(board, "To do")
    a, b, c = [await make_card(client, pm, key, t, stage_id=todo) for t in "ABC"]
    moved = await _move(client, pm, key, c["number"], stage_id=todo, after_id=a["id"])
    assert moved["position"] == (a["position"] + b["position"]) / 2
    assert await _titles(client, pm, key, todo) == ["A", "C", "B"]
    await _move(client, pm, key, a["number"], stage_id=todo, before_id=b["id"])
    assert await _titles(client, pm, key, todo) == ["C", "A", "B"]
    await _move(client, pm, key, c["number"], stage_id=todo)
    assert await _titles(client, pm, key, todo) == ["A", "B", "C"]
    stale = await client.post(
        f"{BOARDS}/{key}/cards/{c['number']}/move",
        json={"stage_id": todo, "after_id": b["id"], "before_id": a["id"]},
        headers=pm.headers,
    )
    assert stale.status_code == 409
    itself = await client.post(
        f"{BOARDS}/{key}/cards/{c['number']}/move",
        json={"stage_id": todo, "after_id": c["id"]},
        headers=pm.headers,
    )
    assert itself.status_code == 422


async def test_a_crowded_stage_is_respaced_and_announced(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    pm, board, key = await _setup(client, pg_session_factory)
    todo = stage_id(board, "To do")
    a, b, c = [await make_card(client, pm, key, t, stage_id=todo) for t in "ABC"]
    epsilon = settings.boards.position_epsilon
    async with pg_session_factory() as db:
        for card, position in ((a, 1.0), (b, 1.0 + epsilon / 4)):
            await db.execute(
                update(BoardCard).where(BoardCard.id == card["id"]).values(position=position)
            )
        await db.commit()
    queue = event_bus.subscribe(f"board:{board['board']['id']}")
    try:
        await _move(client, pm, key, c["number"], stage_id=todo, after_id=a["id"])
        events = []
        while not queue.empty():
            events.append(queue.get_nowait()["data"]["event"])
    finally:
        event_bus.unsubscribe(f"board:{board['board']['id']}", queue)
    assert events == ["stage_reordered", "card_moved"]
    assert await _titles(client, pm, key, todo) == ["A", "C", "B"]
    positions = [c["position"] for c in (await page(client, pm, key, todo))["items"]]
    gap = settings.boards.position_gap
    assert positions == [gap, 1.5 * gap, 2 * gap]


async def test_concurrent_moves_into_one_spot_both_land_in_order(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    pm, board, key = await _setup(client, pg_session_factory)
    todo, doing = stage_id(board, "To do"), stage_id(board, "In progress")
    top, _ = [await make_card(client, pm, key, t, stage_id=doing) for t in ("Top", "Bottom")]
    movers = [await make_card(client, pm, key, f"M{i}", stage_id=todo) for i in range(4)]
    results = await asyncio.gather(
        *(_move(client, pm, key, m["number"], stage_id=doing, after_id=top["id"]) for m in movers)
    )
    assert len({r["position"] for r in results}) == len(movers)
    titles = await _titles(client, pm, key, doing)
    assert titles[0] == "Top" and titles[-1] == "Bottom"
    assert sorted(titles[1:-1]) == ["M0", "M1", "M2", "M3"]


async def test_started_and_completed_follow_the_stages_entered(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    pm, board, key = await _setup(client, pg_session_factory)
    card = await make_card(client, pm, key)
    n = card["number"]
    assert (card["started_at"], card["completed_at"]) == (None, None)
    doing = await _move(client, pm, key, n, stage_id=stage_id(board, "In progress"))
    waiting = await _move(client, pm, key, n, stage_id=stage_id(board, "Waiting"))
    assert doing["started_at"] is not None and waiting["started_at"] == doing["started_at"]
    done = await _move(client, pm, key, n, stage_id=stage_id(board, "Done"))
    assert done["completed_at"] is not None
    reopened = await _move(client, pm, key, n, stage_id=stage_id(board, "To do"))
    assert reopened["completed_at"] is None and reopened["started_at"] == doing["started_at"]
