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

"""WIP and aging from where cards are now, and moves between boards that aren't completions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.config import settings
from app.models.board_card import BoardCard
from app.services import event_bus
from tests.integration.board_api_support import (
    BOARDS,
    Person,
    make_board,
    make_card,
    ok,
    person,
    stage_id,
)
from tests.integration.board_move_board_support import move_board
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration


async def _move(
    client: AsyncClient, who: Person, key: str, card: dict[str, Any], stage: str
) -> None:
    url = f"{BOARDS}/{key}/cards/{card['number']}/move"
    ok(await client.post(url, json={"stage_id": stage}, headers=who.headers))


async def _started(factory: Factory, card: dict[str, Any], days_ago: int) -> None:
    """The card first entered ``in_progress`` ``days_ago`` days ago."""
    async with factory() as db:
        await db.execute(
            update(BoardCard)
            .where(BoardCard.id == uuid.UUID(card["id"]))
            .values(started_at=datetime.now(UTC) - timedelta(days=days_ago))
        )
        await db.commit()


async def test_wip_and_aging_follow_each_cards_stage_now(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    pm = await person(pg_session_factory, await new_org(pg_session_factory), "pm")
    board = await make_board(client, pm)
    key = board["board"]["key"]
    old = await make_card(client, pm, key, "Old")
    fresh = await make_card(client, pm, key, "Fresh")
    queued = await make_card(client, pm, key, "Queued", stage_id=stage_id(board, "To do"))
    for card in (old, fresh):
        await _move(client, pm, key, card, stage_id(board, "In progress"))
    # Old started long ago; going back to To do and in again doesn't restart it.
    await _started(pg_session_factory, old, 30)
    await _move(client, pm, key, old, stage_id(board, "To do"))
    await _move(client, pm, key, old, stage_id(board, "In progress"))
    await _started(pg_session_factory, queued, 30)

    got = ok(await client.get(f"{BOARDS}/{key}/metrics", headers=pm.headers))
    assert got["wip"]["in_progress"] == 2
    assert got["aging_count"] == 1
    assert [a["key"] for a in got["aging"]] == [old["key"]]

    # Re-categorise To do: its card is in progress (and aging) now, with no event.
    url = f"{BOARDS}/{key}/stages/{stage_id(board, 'To do')}"
    ok(await client.patch(url, json={"category": "in_progress"}, headers=pm.headers))
    got = ok(await client.get(f"{BOARDS}/{key}/metrics", headers=pm.headers))
    assert got["wip"]["in_progress"] == 3
    assert got["aging_count"] == 2
    assert [a["key"] for a in got["aging"]] == [old["key"], queued["key"]]
    summary = ok(await client.get(f"{BOARDS}/metrics/summary", headers=pm.headers))
    (row,) = [b for b in summary["boards"] if b["key"] == key]
    assert (row["aging_count"], row["wip"]["in_progress"]) == (2, 3)


async def test_the_aging_list_stops_at_its_limit(
    client: AsyncClient, pg_session_factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings.boards, "metrics_aging_list_limit", 1)
    pm = await person(pg_session_factory, await new_org(pg_session_factory), "pm")
    board = await make_board(client, pm)
    key = board["board"]["key"]
    cards = [await make_card(client, pm, key, f"C{n}") for n in range(3)]
    for days, card in zip((40, 30, 20), cards, strict=True):
        await _move(client, pm, key, card, stage_id(board, "In progress"))
        await _started(pg_session_factory, card, days)

    got = ok(await client.get(f"{BOARDS}/{key}/metrics", headers=pm.headers))
    assert got["aging_count"] == 3
    assert [a["key"] for a in got["aging"]] == [cards[0]["key"]]


async def test_a_done_card_moved_to_a_done_stage_elsewhere_isnt_a_completion(
    client: AsyncClient, pg_session_factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    pm = await person(pg_session_factory, await new_org(pg_session_factory), "pm")
    source, target = await make_board(client, pm), await make_board(client, pm)
    src, dst = source["board"]["key"], target["board"]["key"]
    card = await make_card(client, pm, src, "Shipped")
    await _move(client, pm, src, card, stage_id(source, "In progress"))
    await _move(client, pm, src, card, stage_id(source, "Done"))
    garden: list[dict[str, Any]] = []
    publish = event_bus.publish

    def _publish(topic: str, data: dict[str, Any]) -> None:
        if topic.startswith("board_activity:"):
            garden.append(data)
        publish(topic, data)

    monkeypatch.setattr(event_bus, "publish", _publish)

    moved = ok(await move_board(client, pm, src, card, dst, stage_id=stage_id(target, "Done")))

    assert moved["stage_id"] == stage_id(target, "Done")
    assert garden == []
    got = ok(await client.get(f"{BOARDS}/{dst}/metrics", headers=pm.headers))
    assert sum(w["count"] for w in got["throughput"]) == 0
    assert got["cycle_time"]["count"] == 0
    assert got["wip"]["done"] == 1
