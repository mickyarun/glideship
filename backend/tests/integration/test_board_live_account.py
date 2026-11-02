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

"""Account-wide access changes reach live sockets in every org, in a safe order.

Covers merging a member away, deactivating someone who belongs to two
orgs, the removed member not hearing the event that removed them, a role
lowered mid-upload, and crafted page cursors.
"""

from __future__ import annotations

import asyncio
import base64
import uuid
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

from app.api.v1 import ws_scope_checks
from app.api.v1.ws_subscriptions import ConnectionSubscriptions
from app.core.permissions_boards import BOARDS_VIEW
from app.models.user import OrgToUser
from app.repositories.role import RoleRepository
from app.services.boards import attachment_service
from app.services.ws_topic_policy import ACCESS_CHANGED_KEY, Subscriber
from tests.integration.board_api_support import (
    BOARDS,
    Person,
    card_team,
    make_board,
    ok,
    person,
    put_role,
    use_local_storage,
)
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration

Queue = asyncio.Queue[dict[str, Any]]


@pytest.fixture(autouse=True)
def _socket_sessions(pg_session_factory: Factory, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ws_scope_checks, "AsyncSessionLocal", pg_session_factory)


async def _socket(org: uuid.UUID, who: uuid.UUID, topic: str) -> Queue:
    sub = Subscriber(
        user_id=str(who),
        org_id=str(org),
        has_engineering=False,
        permissions=frozenset({BOARDS_VIEW}),
    )
    send: Queue = asyncio.Queue()
    assert await ConnectionSubscriptions(sub, send).add(topic)
    return send


async def _first(send: Queue) -> dict[str, Any]:
    return await asyncio.wait_for(send.get(), timeout=3)


async def _join(factory: Factory, user: uuid.UUID, org: uuid.UUID, role: str) -> None:
    async with factory() as db:
        found = await RoleRepository(db).get_by_name_system(role)
        assert found is not None
        db.add(OrgToUser(user_id=user, org_id=org, role_id=found.id))
        await db.commit()


async def _org_board(client: AsyncClient, factory: Factory) -> tuple[uuid.UUID, Person, str]:
    org = await new_org(factory)
    admin = await person(factory, org, "org_owner")
    board = (await make_board(client, admin))["board"]
    return org, admin, f"board:{board['id']}"


async def test_merging_a_member_away_drops_the_sources_sockets(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, admin, topic = await _org_board(client, pg_session_factory)
    source, target = [await person(pg_session_factory, org) for _ in range(2)]
    send = await _socket(org, source.id, topic)
    url = f"/api/v1/members/{target.id}/merge"
    ok(await client.post(url, json={"sourceId": str(source.id)}, headers=admin.headers))
    assert await _first(send) == {"topic": topic, "error": "revoked"}


async def test_deactivating_drops_the_sockets_in_every_org(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    home, admin, _ = await _org_board(client, pg_session_factory)
    other, _, other_topic = await _org_board(client, pg_session_factory)
    dev = await person(pg_session_factory, home)
    await _join(pg_session_factory, dev.id, other, "developer")
    send = await _socket(other, dev.id, other_topic)
    ok(await client.patch(f"/api/v1/members/{dev.id}/status", headers=admin.headers))
    assert await _first(send) == {"topic": other_topic, "error": "revoked"}


async def test_a_removed_member_never_hears_the_change_that_removed_them(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    admin = await person(pg_session_factory, org, "org_owner")
    board = (await make_board(client, admin, visibility="members"))["board"]
    key, topic = board["key"], f"board:{board['id']}"
    leaving, staying = [await person(pg_session_factory, org) for _ in range(2)]
    for who in (leaving, staying):
        await put_role(client, admin, key, who.id, "editor")
    gone, kept = [await _socket(org, w.id, topic) for w in (leaving, staying)]

    ok(await client.delete(f"{BOARDS}/{key}/members/{leaving.id}", headers=admin.headers))
    assert await _first(gone) == {"topic": topic, "error": "revoked"}
    heard = (await _first(kept))["data"]
    assert heard["event"] == "member_changed" and ACCESS_CHANGED_KEY not in heard
    await asyncio.sleep(0.2)
    assert gone.empty()


async def test_an_upload_refused_when_the_role_is_lowered_mid_upload(
    client: AsyncClient,
    pg_session_factory: Factory,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_local_storage(tmp_path, monkeypatch)
    team = await card_team(client, pg_session_factory)
    real_store = attachment_service.store

    async def _store_then_demote(*args: Any, **kwargs: Any) -> Any:
        stored = await real_store(*args, **kwargs)
        await put_role(client, team.admin, team.key, team.editor.id, "viewer")
        return stored

    monkeypatch.setattr(attachment_service, "store", _store_then_demote)
    url = f"{team.url}/attachments"
    files = {"file": ("shot.png", b"\x89PNG data", "application/octet-stream")}
    assert (await client.post(url, files=files, headers=team.editor.headers)).status_code == 403
    assert ok(await client.get(url, headers=team.viewer.headers))["items"] == []
    assert [p for p in tmp_path.rglob("*") if p.is_file()] == []


@pytest.mark.parametrize(
    ("listing", "parts"),
    [
        ("comments", '["2026-10-29T12:30:00","{row}"]'),
        ("comments", '["0001-01-01T00:00:00+01:00","{row}"]'),
        ("cards", '[NaN,"{row}"]'),
        ("cards", '[Infinity,"{row}"]'),
    ],
)
async def test_crafted_cursors_are_refused(
    client: AsyncClient, pg_session_factory: Factory, listing: str, parts: str
) -> None:
    team = await card_team(client, pg_session_factory)
    cursor = base64.urlsafe_b64encode(parts.format(row=uuid.uuid4()).encode()).decode()
    if listing == "comments":
        url, params = f"{team.url}/comments", {"cursor": cursor}
    else:
        url, params = f"{BOARDS}/{team.key}/cards", {"cursor": cursor, "q": "x"}
    resp = await client.get(url, params=params, headers=team.viewer.headers)
    assert resp.status_code == 422, resp.text
