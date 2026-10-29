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

"""Board members and teams: roles, the last admin, and live access being revoked."""

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
from app.services.boards.member_service import LAST_ADMIN
from app.services.ws_topic_policy import Subscriber
from tests.integration.board_api_support import BOARDS, make_board, ok, person, put_role
from tests.integration.board_support import new_team
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration

VIEW_ONLY = frozenset({BOARDS_VIEW})


@pytest.fixture(autouse=True)
def _socket_sessions(pg_session_factory: Factory, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ws_scope_checks, "AsyncSessionLocal", pg_session_factory)


async def test_people_and_teams_get_roles(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    dev = await person(pg_session_factory, org)
    team = await new_team(pg_session_factory, org, dev.id)
    key = (await make_board(client, pm, visibility="members"))["board"]["key"]
    url = f"{BOARDS}/{key}"
    assert (await client.get(url, headers=dev.headers)).status_code == 404

    teams = ok(
        await client.put(f"{url}/teams/{team}", json={"role": "editor"}, headers=pm.headers)
    )
    assert [(t["team_id"], t["role"]) for t in teams["teams"]] == [(str(team), "editor")]
    assert ok(await client.get(url, headers=dev.headers))["role"] == "editor"
    await put_role(client, pm, key, dev.id, "admin")
    assert ok(await client.get(url, headers=dev.headers))["role"] == "admin"
    await put_role(client, pm, key, dev.id, "viewer")
    assert ok(await client.get(url, headers=dev.headers))["role"] == "editor"  # the team's

    ok(await client.delete(f"{url}/members/{dev.id}", headers=pm.headers))
    ok(await client.delete(f"{url}/teams/{team}", headers=pm.headers))
    assert (await client.get(url, headers=dev.headers)).status_code == 404
    gone = await client.delete(f"{url}/members/{dev.id}", headers=pm.headers)
    assert gone.status_code == 404


async def test_only_org_members_and_teams_can_be_added(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, other = await new_org(pg_session_factory), await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    stranger = await person(pg_session_factory, other)
    their_team = await new_team(pg_session_factory, other)
    url = f"{BOARDS}/{(await make_board(client, pm))['board']['key']}"
    member = await client.put(
        f"{url}/members/{stranger.id}", json={"role": "viewer"}, headers=pm.headers
    )
    team = await client.put(
        f"{url}/teams/{their_team}", json={"role": "viewer"}, headers=pm.headers
    )
    assert (member.status_code, team.status_code) == (404, 404)


async def test_the_last_admin_stays(client: AsyncClient, pg_session_factory: Factory) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    dev = await person(pg_session_factory, org)
    key = (await make_board(client, pm))["board"]["key"]
    url = f"{BOARDS}/{key}/members/{pm.id}"
    for resp in (
        await client.put(url, json={"role": "editor"}, headers=pm.headers),
        await client.delete(url, headers=pm.headers),
    ):
        assert (resp.status_code, resp.json()) == (409, {"detail": LAST_ADMIN})

    team = await new_team(pg_session_factory, org, dev.id)
    ok(
        await client.put(
            f"{BOARDS}/{key}/teams/{team}", json={"role": "admin"}, headers=pm.headers
        )
    )
    ok(await client.put(url, json={"role": "editor"}, headers=pm.headers))
    team_url = f"{BOARDS}/{key}/teams/{team}"
    assert (await client.delete(team_url, headers=dev.headers)).status_code == 409


def _socket(
    org: uuid.UUID, user: uuid.UUID, topic: str
) -> tuple[ConnectionSubscriptions, asyncio.Queue[Any]]:
    """A socket for ``user`` holding ``topic``, checked by the real scope check."""
    who = Subscriber(
        user_id=str(user), org_id=str(org), has_engineering=False, permissions=VIEW_ONLY
    )
    send: asyncio.Queue[Any] = asyncio.Queue()
    subs = ConnectionSubscriptions(who, send, ws_scope_checks.passes_scope_check)
    subs.add(topic)
    return subs, send


async def _revoked(send: asyncio.Queue[Any]) -> dict[str, Any]:
    while True:
        message = await asyncio.wait_for(send.get(), timeout=2)
        if message.get("error") == "revoked":
            return dict(message)


async def test_removing_someone_drops_their_board_socket(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    dev, stays = [await person(pg_session_factory, org) for _ in range(2)]
    board = await make_board(client, pm, visibility="members")
    key, board_id = board["board"]["key"], board["board"]["id"]
    for who in (dev, stays):
        await put_role(client, pm, key, who.id, "editor")

    topic = f"board:{board_id}"
    (dev_subs, dev_send), (stay_subs, stay_send) = [
        _socket(org, who.id, topic) for who in (dev, stays)
    ]
    await asyncio.sleep(0.05)

    ok(await client.delete(f"{BOARDS}/{key}/members/{dev.id}", headers=pm.headers))
    assert await _revoked(dev_send) == {"topic": topic, "error": "revoked"}
    assert dev_subs.topics == frozenset()
    await asyncio.sleep(0.05)
    assert stay_subs.topics == frozenset({topic})

    # The next change on the board reaches only the person who still has access.
    while not stay_send.empty():
        stay_send.get_nowait()
    event_bus.publish(topic, {"event": "card_created"})
    assert (await asyncio.wait_for(stay_send.get(), timeout=2))["data"]["event"] == "card_created"
    assert dev_send.empty()
    dev_subs.close()
    stay_subs.close()


async def test_hiding_a_board_rechecks_every_socket(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    reader = await person(pg_session_factory, org, "sales")
    board = await make_board(client, pm)
    key, board_id = board["board"]["key"], board["board"]["id"]
    subs, send = _socket(org, reader.id, f"board:{board_id}")
    await asyncio.sleep(0.05)
    ok(await client.patch(f"{BOARDS}/{key}", json={"visibility": "members"}, headers=pm.headers))
    await _revoked(send)
    assert subs.topics == frozenset()
