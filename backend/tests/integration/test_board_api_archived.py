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


"""Archived boards: ``GET /boards?archived=true`` lists them by the rule their pages use."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from tests.integration.board_api_support import BOARDS, Person, make_board, ok, person, put_role
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration


async def _keys(client: AsyncClient, who: Person, **params: Any) -> list[str]:
    body = ok(await client.get(BOARDS, params=params, headers=who.headers))
    return [i.get("key", i["kind"]) for i in body["items"]]


async def _switcher_keys(client: AsyncClient, who: Person) -> set[str]:
    body = ok(await client.get(f"{BOARDS}/switcher", headers=who.headers))
    return {i["key"] for group in ("starred", "recent", "other") for i in body[group]}


async def test_archived_boards_are_listed_to_whoever_holds_a_role_on_them(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    viewer, member = [await person(pg_session_factory, org, "sales") for _ in range(2)]
    org_admin = await person(pg_session_factory, org, "admin")
    outsider = await person(pg_session_factory, await new_org(pg_session_factory), "admin")
    shown = (await make_board(client, pm, name="A shown"))["board"]["key"]
    hidden = (await make_board(client, pm, name="B hidden", visibility="members"))["board"]
    live = (await make_board(client, pm, name="C live"))["board"]["key"]
    await put_role(client, pm, hidden["key"], member.id, "viewer")
    for key in (shown, hidden["key"]):
        ok(await client.post(f"{BOARDS}/{key}/archive", headers=pm.headers))

    assert await _keys(client, pm, archived="true") == [shown, hidden["key"]]
    assert await _keys(client, org_admin, archived="true") == [shown, hidden["key"]]
    assert await _keys(client, viewer, archived="true") == [shown]
    assert await _keys(client, member, archived="true") == [shown, hidden["key"]]
    assert await _keys(client, outsider, archived="true") == []
    # The default list and the switcher stay active-only, Delivery included.
    assert await _keys(client, pm) == [live, "delivery"]
    assert await _keys(client, viewer, archived="false") == [live]
    assert await _switcher_keys(client, pm) == {live}

    listed = ok(await client.get(BOARDS, params={"archived": "true"}, headers=pm.headers))
    assert [i["role"] for i in listed["items"]] == ["admin", "admin"]


async def test_an_archived_board_opens_read_only_and_only_admins_restore_it(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    viewer = await person(pg_session_factory, org, "sales")
    url = f"{BOARDS}/{(await make_board(client, pm))['board']['key']}"
    ok(await client.post(f"{url}/archive", headers=pm.headers))

    opened = ok(await client.get(url, headers=viewer.headers))
    assert (opened["board"]["status"], opened["capabilities"]) == ("archived", ["view"])
    assert (await client.post(f"{url}/restore", headers=viewer.headers)).status_code == 403
    ok(await client.post(f"{url}/restore", headers=pm.headers))
    assert await _keys(client, viewer, archived="true") == []
