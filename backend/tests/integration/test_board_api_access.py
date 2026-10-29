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

"""Every board route, called by each kind of caller: 404, 403 and 409 where they belong.

The matrix is built from the routes themselves (their ``require_board``
role and ``writable`` flag), so a new route is covered without a new test.
"""

from __future__ import annotations

import re
import uuid

import pytest
from httpx import AsyncClient

from app.models.board_enums import BoardMemberRole
from tests.api.test_board_routes import board_dep, board_routes
from tests.integration.board_api_support import (
    BOARDS,
    Person,
    make_board,
    make_card,
    ok,
    person,
    put_role,
)
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration

VIEWER, EDITOR, ADMIN = BoardMemberRole.VIEWER, BoardMemberRole.EDITOR, BoardMemberRole.ADMIN


def _url(path: str, key: str, number: int) -> str:
    fixed = {"key": key, "number": str(number), "kind": "prd", "version": "1"}
    return re.sub(r"\{(\w+)\}", lambda m: fixed.get(m.group(1), str(uuid.uuid4())), path)


async def _status(client: AsyncClient, method: str, url: str, who: Person) -> int:
    return (await client.request(method, url, json={}, headers=who.headers)).status_code


async def test_each_route_answers_404_403_and_409_by_caller(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, other = await new_org(pg_session_factory), await new_org(pg_session_factory)
    admin = await person(pg_session_factory, org, "manager")
    board = await make_board(client, admin, visibility="members")
    key = board["board"]["key"]
    card = await make_card(client, admin, key)
    viewer, editor, outsider = [await person(pg_session_factory, org) for _ in range(3)]
    await put_role(client, admin, key, viewer.id, "viewer")
    await put_role(client, admin, key, editor.id, "editor")
    foreigner = await person(pg_session_factory, other, "manager")

    keyed = [r for r in board_routes() if "{key}" in r.path]
    assert len(keyed) > 40
    for route in keyed:
        (method,) = route.methods
        url, need = _url(route.path, key, card["number"]), board_dep(route).board_min_role
        for stranger in (outsider, foreigner):
            assert await _status(client, method, url, stranger) == 404, (method, url)
        if need is not VIEWER:
            assert await _status(client, method, url, viewer) == 403, (method, url)
        if need is ADMIN:
            assert await _status(client, method, url, editor) == 403, (method, url)

    ok(await client.post(f"{BOARDS}/{key}/archive", headers=admin.headers))
    for route in keyed:
        (method,) = route.methods
        if method != "GET" and board_dep(route).board_writable:
            url = _url(route.path, key, card["number"])
            assert await _status(client, method, url, admin) == 409, (method, url)


async def test_an_org_board_is_readable_by_everyone_with_boards_view(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    admin = await person(pg_session_factory, org, "manager")
    key = (await make_board(client, admin))["board"]["key"]
    sales = await person(pg_session_factory, org, "sales")
    body = ok(await client.get(f"{BOARDS}/{key}", headers=sales.headers))
    assert body["role"] == "viewer"
    assert body["capabilities"] == ["view", "comment"]
    resp = await client.post(f"{BOARDS}/{key}/cards", json={"title": "x"}, headers=sales.headers)
    assert resp.status_code == 403
