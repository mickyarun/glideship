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

"""Open boards hear about derived card facts and about who can open the board.

Saving a document or changing the checklist announces the card's fresh
summary, so a board checks stage entry rules against what's true now. A
change to a board's people, its teams or a team's members announces
``people_changed`` on every board it touches.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import AsyncClient

from app.services import event_bus
from tests.integration.board_api_support import (
    BOARDS,
    Person,
    make_board,
    make_card,
    ok,
    person,
    put_role,
)
from tests.integration.board_support import new_team
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration

Queue = asyncio.Queue[dict[str, Any]]


@pytest.fixture
async def listen() -> AsyncIterator[Any]:
    """Subscribe to board topics for the test; unsubscribed afterwards."""
    held: list[tuple[str, Queue]] = []

    def _listen(board: dict[str, Any]) -> Queue:
        topic = f"board:{board['board']['id']}"
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


async def _admin(client: AsyncClient, factory: Factory) -> tuple[uuid.UUID, Person]:
    org = await new_org(factory)
    return org, await person(factory, org, "org_owner")


async def test_saving_a_prd_announces_the_card_summary_with_has_prd(
    client: AsyncClient, pg_session_factory: Factory, listen: Any
) -> None:
    _, admin = await _admin(client, pg_session_factory)
    board = await make_board(client, admin)
    card = await make_card(client, admin, board["board"]["key"])
    assert card["has_prd"] is False
    queue = listen(board)
    url = f"{BOARDS}/{board['board']['key']}/cards/{card['number']}/docs/prd"
    body = {"body_md": "# Why", "base_version": None}
    ok(await client.put(url, json=body, headers=admin.headers))

    events = await _events(queue)
    assert [e["event"] for e in events] == ["doc_updated", "card_updated"]
    assert events[1]["card"]["id"] == card["id"]
    assert events[1]["card"]["has_prd"] is True


async def test_checklist_changes_announce_fresh_counts(
    client: AsyncClient, pg_session_factory: Factory, listen: Any
) -> None:
    _, admin = await _admin(client, pg_session_factory)
    board = await make_board(client, admin)
    card = await make_card(client, admin, board["board"]["key"])
    url = f"{BOARDS}/{board['board']['key']}/cards/{card['number']}/checklist"
    queue = listen(board)
    item = ok(await client.post(url, json={"text": "Ship"}, headers=admin.headers), 201)
    ok(await client.patch(f"{url}/{item['id']}", json={"done": True}, headers=admin.headers))
    resp = await client.delete(f"{url}/{item['id']}", headers=admin.headers)
    assert resp.status_code == 204, resp.text

    events = await _events(queue)
    assert [e["event"] for e in events] == ["card_updated"] * 3
    counts = [(e["card"]["checklist_done"], e["card"]["checklist_total"]) for e in events]
    assert counts == [(0, 1), (1, 1), (0, 0)]


async def test_board_member_and_team_changes_announce_people_changed(
    client: AsyncClient, pg_session_factory: Factory, listen: Any
) -> None:
    org, admin = await _admin(client, pg_session_factory)
    dev = await person(pg_session_factory, org)
    team = await new_team(pg_session_factory, org)
    board = await make_board(client, admin, visibility="members")
    key = board["board"]["key"]
    queue = listen(board)
    await put_role(client, admin, key, dev.id, "editor")
    ok(
        await client.put(
            f"{BOARDS}/{key}/teams/{team}", json={"role": "viewer"}, headers=admin.headers
        )
    )
    ok(await client.delete(f"{BOARDS}/{key}/teams/{team}", headers=admin.headers))
    ok(await client.delete(f"{BOARDS}/{key}/members/{dev.id}", headers=admin.headers))

    events = await _events(queue)
    assert [e["event"] for e in events] == ["member_changed", "people_changed"] * 4
    assert set(events[1]) == {"event", "actor_id", "origin"}


async def test_team_membership_changes_reach_every_board_that_grants_the_team(
    client: AsyncClient, pg_session_factory: Factory, listen: Any
) -> None:
    org, admin = await _admin(client, pg_session_factory)
    dev = await person(pg_session_factory, org)
    team = await new_team(pg_session_factory, org)
    granting = [await make_board(client, admin, visibility="members") for _ in range(2)]
    other = await make_board(client, admin, visibility="members")
    for board in granting:
        url = f"{BOARDS}/{board['board']['key']}/teams/{team}"
        ok(await client.put(url, json={"role": "editor"}, headers=admin.headers))
    queues = [listen(b) for b in (*granting, other)]

    members = f"/api/v1/teams/{team}/members"
    resp = await client.post(members, json={"user_id": str(dev.id)}, headers=admin.headers)
    assert resp.status_code == 201, resp.text
    resp = await client.delete(f"{members}/{dev.id}", headers=admin.headers)
    assert resp.status_code == 204, resp.text

    heard = [await _events(q) for q in queues]
    for events in heard[:2]:
        assert [e["event"] for e in events] == ["people_changed", "people_changed"]
    assert heard[2] == []
