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

"""What a board topic carries, and that nothing goes out unless the change commits."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.boards.card import CardSummary
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
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration

Queue = asyncio.Queue[dict[str, Any]]
SUMMARY_FIELDS = set(CardSummary.model_fields)


async def _setup(client: AsyncClient, factory: Factory) -> tuple[Person, dict[str, Any], str, str]:
    org = await new_org(factory)
    pm = await person(factory, org, "pm")
    board = await make_board(client, pm, template="ops")
    return pm, board, board["board"]["key"], f"board:{board['board']['id']}"


@pytest.fixture
async def listen() -> AsyncIterator[Any]:
    """Subscribe to topics for the test; unsubscribed afterwards."""
    held: list[tuple[str, Queue]] = []

    def _listen(topic: str) -> Queue:
        queue = event_bus.subscribe(topic)
        held.append((topic, queue))
        return queue

    yield _listen
    for topic, queue in held:
        event_bus.unsubscribe(topic, queue)


async def _events(queue: Queue) -> list[dict[str, Any]]:
    await asyncio.sleep(0)
    found = []
    while not queue.empty():
        found.append(queue.get_nowait()["data"])
    return found


async def test_card_events_carry_the_summary_and_the_actor(
    client: AsyncClient, pg_session_factory: Factory, listen: Any
) -> None:
    pm, board, key, topic = await _setup(client, pg_session_factory)
    queue = listen(topic)
    card = await make_card(client, pm, key, "Watch me")
    url = f"{BOARDS}/{key}/cards/{card['number']}"
    ok(await client.patch(url, json={"title": "Watched"}, headers=pm.headers))
    ok(await client.post(f"{url}/archive", headers=pm.headers))
    stage = stage_id(board, "Waiting")
    body = {"wip_limit": 2}
    ok(await client.patch(f"{BOARDS}/{key}/stages/{stage}", json=body, headers=pm.headers))

    events = await _events(queue)
    assert [e["event"] for e in events] == [
        "card_created",
        "card_updated",
        "card_archived",
        "stage_changed",
    ]
    assert all(e["actor_id"] == str(pm.id) for e in events)
    for event in events[:3]:
        assert set(event["card"]) == SUMMARY_FIELDS
        assert event["card"]["id"] == card["id"]
    assert events[1]["card"]["title"] == "Watched"
    assert set(events[3]) == {"event", "actor_id", "origin"}
    assert all(e["origin"] is None for e in events)


async def test_a_change_that_fails_to_commit_announces_nothing(
    client: AsyncClient,
    pg_session_factory: Factory,
    listen: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pm, _, key, topic = await _setup(client, pg_session_factory)
    queue = listen(topic)

    async def _fail(self: AsyncSession) -> None:
        raise RuntimeError("commit failed")

    with monkeypatch.context() as patch:
        patch.setattr(AsyncSession, "commit", _fail)
        with pytest.raises(RuntimeError):
            await client.post(f"{BOARDS}/{key}/cards", json={"title": "Lost"}, headers=pm.headers)
    assert await _events(queue) == []
    await make_card(client, pm, key, "Kept")
    events = await _events(queue)
    assert [(e["event"], e["card"]["title"]) for e in events] == [("card_created", "Kept")]


async def test_a_refused_move_announces_nothing(
    client: AsyncClient, pg_session_factory: Factory, listen: Any
) -> None:
    pm, board, key, topic = await _setup(client, pg_session_factory)
    card = await make_card(client, pm, key)
    url = f"{BOARDS}/{key}/cards/{card['number']}"
    ok(await client.post(f"{url}/archive", headers=pm.headers))
    queue = listen(topic)
    move = {"stage_id": stage_id(board, "Done")}
    assert (await client.post(f"{url}/move", json=move, headers=pm.headers)).status_code == 409
    assert await _events(queue) == []


async def test_events_name_the_tab_that_made_the_change(
    client: AsyncClient, pg_session_factory: Factory, listen: Any
) -> None:
    pm, board, key, topic = await _setup(client, pg_session_factory)
    queue = listen(topic)
    tab = "6f1c2a9e-4d0b-4c7e-9a31-0b5d2e8f7c11"
    card = await make_card(client, pm, key, "Mine")
    url = f"{BOARDS}/{key}/cards/{card['number']}"
    headers = {**pm.headers, "X-Client-Id": tab}
    ok(await client.patch(url, json={"title": "Still mine"}, headers=headers))
    bad = {**pm.headers, "X-Client-Id": "not a client id!"}
    ok(await client.patch(url, json={"title": "Dropped id"}, headers=bad))
    events = await _events(queue)
    assert [e["origin"] for e in events] == [None, tab, None]


async def test_a_move_names_the_stage_it_left(
    client: AsyncClient, pg_session_factory: Factory, listen: Any
) -> None:
    pm, board, key, topic = await _setup(client, pg_session_factory)
    card = await make_card(client, pm, key)
    queue = listen(topic)
    move = {"stage_id": stage_id(board, "Done")}
    url = f"{BOARDS}/{key}/cards/{card['number']}/move"
    ok(await client.post(url, json=move, headers=pm.headers))
    (moved,) = [e for e in await _events(queue) if e["event"] == "card_moved"]
    assert moved["from_stage_id"] == card["stage_id"]
    assert moved["card"]["stage_id"] == move["stage_id"]
