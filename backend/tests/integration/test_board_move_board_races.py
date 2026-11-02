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


"""Moves between boards under contention: crossing moves, deleted labels, the move budget."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, func, select

from app.config import settings
from app.models.board import BoardLabel
from app.models.board_card import BoardCardKeyAlias
from app.services import fixed_window
from tests.integration.board_api_support import BOARDS, make_card, ok
from tests.integration.board_move_board_support import label, move_board, two_boards
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration
BY_KEY = f"{BOARDS}/cards/by-key"
UNKNOWN_LABEL = "Labels must be labels of this board."


async def test_crossing_moves_both_land_with_distinct_numbers(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    two = await two_boards(client, pg_session_factory)
    pm, a, b = two.pm, two.src, two.dst
    on_a = await make_card(client, pm, a, "From A")
    on_b = await make_card(client, pm, b, "From B")
    there, back = await asyncio.wait_for(
        asyncio.gather(
            move_board(client, pm, a, on_a, b),
            move_board(client, pm, b, on_b, a),
        ),
        timeout=30,
    )
    to_b, to_a = ok(there), ok(back)
    assert to_b["board_key"] == b and to_a["board_key"] == a
    assert to_b["number"] != on_b["number"] and to_a["number"] != on_a["number"]
    # The new numbers are fresh on each board, never reused.
    assert to_b["number"] == 2 and to_a["number"] == 2


async def test_there_and_back_takes_a_fresh_number_and_both_old_keys_resolve(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    two = await two_boards(client, pg_session_factory)
    pm = two.pm
    card = await make_card(client, pm, two.src, "Round trip")
    there = ok(await move_board(client, pm, two.src, card, two.dst))
    home = ok(await move_board(client, pm, two.dst, there, two.src))
    assert home["board_key"] == two.src and home["number"] != card["number"]
    for old in (card["key"], there["key"]):
        found = ok(await client.get(f"{BY_KEY}/{old}", headers=pm.headers))
        assert (found["id"], found["key"]) == (card["id"], home["key"])
    async with pg_session_factory() as db:
        aliases = await db.scalar(
            select(func.count())
            .select_from(BoardCardKeyAlias)
            .where(BoardCardKeyAlias.card_id == uuid.UUID(card["id"]))
        )
    assert aliases == 2


async def _delete_label_meanwhile(factory: Factory, label_id: str, request: Any) -> Any:
    """Delete the label in a second session, holding it until ``request`` is under way."""
    async with factory() as db:
        await db.execute(delete(BoardLabel).where(BoardLabel.id == uuid.UUID(label_id)))
        pending = asyncio.ensure_future(request)
        # Let the request reach the label before the delete commits.
        await asyncio.sleep(0.5)
        await db.commit()
    return await asyncio.wait_for(pending, timeout=30)


async def test_a_label_deleted_mid_edit_is_refused_like_an_unknown_one(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    two = await two_boards(client, pg_session_factory)
    card = await make_card(client, two.pm, two.src)
    doomed = await label(client, two.pm, two.src, "Doomed")
    url = f"{BOARDS}/{two.src}/cards/{card['number']}"
    patch = client.patch(url, json={"label_ids": [doomed]}, headers=two.pm.headers)
    resp = await _delete_label_meanwhile(pg_session_factory, doomed, patch)
    assert resp.status_code == 422 and resp.json()["detail"] == UNKNOWN_LABEL
    gone = await label(client, two.pm, two.src, "Gone")
    body = {"title": "New", "label_ids": [gone]}
    create = client.post(f"{BOARDS}/{two.src}/cards", json=body, headers=two.pm.headers)
    made = await _delete_label_meanwhile(pg_session_factory, gone, create)
    assert made.status_code == 422 and made.json()["detail"] == UNKNOWN_LABEL


async def test_a_label_deleted_mid_move_is_dropped_and_listed(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    two = await two_boards(client, pg_session_factory)
    pm = two.pm
    mine = await label(client, pm, two.src, "Bug")
    theirs = await label(client, pm, two.dst, "bug")
    card = await make_card(client, pm, two.src, label_ids=[mine])
    resp = await _delete_label_meanwhile(
        pg_session_factory, theirs, move_board(client, pm, two.src, card, two.dst)
    )
    moved = ok(resp)
    assert moved["label_ids"] == []
    events = f"{BOARDS}/{two.dst}/cards/{moved['number']}/events"
    history = ok(await client.get(events, headers=pm.headers))
    (entry,) = [e for e in history["items"] if e["type"] == "moved_board"]
    assert entry["detail"]["dropped_labels"] == ["Bug"]


class _Counter:
    """Just enough of Redis for the fixed-window limiter."""

    def __init__(self) -> None:
        self.hits: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.hits[key] = self.hits.get(key, 0) + 1
        return self.hits[key]

    async def expire(self, _key: str, _seconds: int) -> bool:
        return True


async def test_too_many_moves_in_a_window_get_429_with_retry_after(
    client: AsyncClient, pg_session_factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    counter = _Counter()

    async def _redis() -> _Counter:
        return counter

    monkeypatch.setattr(fixed_window, "get_redis", _redis)
    monkeypatch.setattr(settings.boards, "move_board_limit", 2)
    two = await two_boards(client, pg_session_factory)
    cards = [await make_card(client, two.pm, two.src, f"C{n}") for n in range(3)]
    for card in cards[:2]:
        ok(await move_board(client, two.pm, two.src, card, two.dst))
    limited = await move_board(client, two.pm, two.src, cards[2], two.dst)
    assert limited.status_code == 429
    assert 1 <= int(limited.headers["Retry-After"]) <= settings.boards.move_board_window_seconds
    url = f"{BOARDS}/{two.src}/cards/{cards[2]['number']}"
    still = ok(await client.get(url, headers=two.pm.headers))
    assert still["board_key"] == two.src
