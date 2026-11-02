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

"""Live board sockets lose access on every path that takes it away, and keep it otherwise.

Each socket uses the process hub and the real holder check (committed roles).
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest
from httpx import AsyncClient

from app.api.v1 import ws_scope_checks
from app.api.v1.ws_subscriptions import ConnectionSubscriptions
from app.core.permissions_boards import BOARDS_VIEW
from app.services import event_bus
from app.services.ws_topic_policy import Subscriber, access_topic
from tests.integration.board_api_support import (
    BOARDS,
    Person,
    custom_role,
    make_board,
    ok,
    person,
    put_role,
)
from tests.integration.board_support import new_team
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration

Queue = asyncio.Queue[dict[str, Any]]


@pytest.fixture(autouse=True)
def _socket_sessions(pg_session_factory: Factory, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ws_scope_checks, "AsyncSessionLocal", pg_session_factory)


async def _socket(
    org: uuid.UUID, who: Person, topic: str
) -> tuple[ConnectionSubscriptions, Queue]:
    """A socket for ``who`` holding ``topic``, admitted by the real checks."""
    sub = Subscriber(
        user_id=str(who.id),
        org_id=str(org),
        has_engineering=False,
        permissions=frozenset({BOARDS_VIEW}),
    )
    assert await ws_scope_checks.passes_scope_check(topic, sub)
    send: Queue = asyncio.Queue()
    subs = ConnectionSubscriptions(sub, send)
    assert await subs.add(topic)
    return subs, send


async def _revoked(send: Queue) -> dict[str, Any]:
    while True:
        message = await asyncio.wait_for(send.get(), timeout=3)
        if message.get("error") == "revoked":
            return message


async def _still_live(subs: ConnectionSubscriptions, send: Queue, topic: str) -> None:
    """Ask everyone to re-check, then prove ``subs`` still receives the topic."""
    control = access_topic(topic)
    assert control is not None
    event_bus.publish(control, {"user_ids": None})
    marker = {"event": f"probe-{uuid.uuid4()}"}
    for _ in range(50):
        event_bus.publish(topic, marker)
        message = await asyncio.wait_for(send.get(), timeout=3)
        assert message.get("error") != "revoked"
        if message.get("data") == marker:
            break
    assert topic in subs.topics


async def _board(client: AsyncClient, factory: Factory) -> tuple[uuid.UUID, Person, str, str]:
    org = await new_org(factory)
    admin = await person(factory, org, "org_owner")
    board = (await make_board(client, admin, visibility="members"))["board"]
    return org, admin, board["key"], f"board:{board['id']}"


async def test_removing_a_person_drops_only_their_socket(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, admin, key, topic = await _board(client, pg_session_factory)
    leaving, staying = [await person(pg_session_factory, org) for _ in range(2)]
    for who in (leaving, staying):
        await put_role(client, admin, key, who.id, "editor")
    (gone, gone_send), (kept, kept_send) = [
        await _socket(org, w, topic) for w in (leaving, staying)
    ]

    ok(await client.delete(f"{BOARDS}/{key}/members/{leaving.id}", headers=admin.headers))
    assert await _revoked(gone_send) == {"topic": topic, "error": "revoked"}
    assert gone.topics == frozenset()
    await _still_live(kept, kept_send, topic)
    gone.close()
    kept.close()


async def test_a_team_role_keeps_the_socket_when_the_own_row_goes(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, admin, key, topic = await _board(client, pg_session_factory)
    dev = await person(pg_session_factory, org)
    team = await new_team(pg_session_factory, org, dev.id)
    ok(
        await client.put(
            f"{BOARDS}/{key}/teams/{team}", json={"role": "viewer"}, headers=admin.headers
        )
    )
    await put_role(client, admin, key, dev.id, "editor")
    subs, send = await _socket(org, dev, topic)
    ok(await client.delete(f"{BOARDS}/{key}/members/{dev.id}", headers=admin.headers))
    await _still_live(subs, send, topic)

    ok(await client.delete(f"{BOARDS}/{key}/teams/{team}", headers=admin.headers))
    await _revoked(send)
    subs.close()


@pytest.mark.parametrize("how", ["leave team", "archive team"])
async def test_team_changes_drop_the_members_sockets(
    client: AsyncClient, pg_session_factory: Factory, how: str
) -> None:
    org, admin, key, topic = await _board(client, pg_session_factory)
    dev = await person(pg_session_factory, org)
    team = await new_team(pg_session_factory, org, dev.id)
    ok(
        await client.put(
            f"{BOARDS}/{key}/teams/{team}", json={"role": "editor"}, headers=admin.headers
        )
    )
    subs, send = await _socket(org, dev, topic)
    if how == "leave team":
        resp = await client.delete(f"/api/v1/teams/{team}/members/{dev.id}", headers=admin.headers)
    else:
        resp = await client.delete(f"/api/v1/teams/{team}", headers=admin.headers)
    assert resp.status_code < 300, resp.text
    await _revoked(send)
    subs.close()


async def test_losing_boards_view_or_the_account_drops_the_socket(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, admin, _, _ = await _board(client, pg_session_factory)
    shown = (await make_board(client, admin))["board"]
    topic = f"board:{shown['id']}"
    demoted, deactivated = [await person(pg_session_factory, org) for _ in range(2)]
    (role_subs, role_send), (gone_subs, gone_send) = [
        await _socket(org, w, topic) for w in (demoted, deactivated)
    ]
    # A custom role without boards:view, assigned through the members API.
    role = await custom_role(pg_session_factory, org, "leave:request")
    url = f"/api/v1/members/{demoted.id}/role"
    ok(await client.patch(url, json={"roleId": str(role)}, headers=admin.headers))
    await _revoked(role_send)

    ok(await client.patch(f"/api/v1/members/{deactivated.id}/status", headers=admin.headers))
    await _revoked(gone_send)
    role_subs.close()
    gone_subs.close()


async def test_hiding_a_board_drops_org_viewers(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    reader = await person(pg_session_factory, org, "sales")
    board = (await make_board(client, pm))["board"]
    subs, send = await _socket(org, reader, f"board:{board['id']}")
    ok(
        await client.patch(
            f"{BOARDS}/{board['key']}", json={"visibility": "members"}, headers=pm.headers
        )
    )
    await _revoked(send)
    assert subs.topics == frozenset()
