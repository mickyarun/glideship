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

"""The team picker on a board's settings: the org's teams, for board admins only."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.models.team import TeamStatus
from tests.integration.board_api_support import BOARDS, make_board, ok, person, put_role
from tests.integration.board_support import new_team
from tests.integration.leave_support import give_custom_role
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration


async def test_a_board_admin_without_team_view_lists_the_orgs_teams(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    admin, a, b = [await person(pg_session_factory, org) for _ in range(3)]
    await give_custom_role(pg_session_factory, org, admin.id, "boards:view")
    big = await new_team(pg_session_factory, org, a.id, b.id)
    empty = await new_team(pg_session_factory, org)
    await new_team(pg_session_factory, org, a.id, status=TeamStatus.ARCHIVED)
    other_org = await new_org(pg_session_factory)
    stranger = await person(pg_session_factory, other_org)
    await new_team(pg_session_factory, other_org, stranger.id)
    key = (await make_board(client, pm))["board"]["key"]
    await put_role(client, pm, key, admin.id, "admin")

    items = ok(await client.get(f"{BOARDS}/{key}/teams/options", headers=admin.headers))["items"]
    # Only this org's active teams, each with its size; another org's never appear.
    assert {i["id"]: i["member_count"] for i in items} == {str(big): 2, str(empty): 0}
    assert [i["name"] for i in items] == sorted(i["name"] for i in items)


async def test_editors_and_viewers_are_refused(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    editor, viewer = [await person(pg_session_factory, org) for _ in range(2)]
    key = (await make_board(client, pm))["board"]["key"]
    await put_role(client, pm, key, editor.id, "editor")
    await put_role(client, pm, key, viewer.id, "viewer")
    for who in (editor, viewer):
        resp = await client.get(f"{BOARDS}/{key}/teams/options", headers=who.headers)
        assert resp.status_code == 403, resp.text


async def test_a_members_only_board_is_not_found_for_others(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    outsider = await person(pg_session_factory, org)
    key = (await make_board(client, pm, visibility="members"))["board"]["key"]
    resp = await client.get(f"{BOARDS}/{key}/teams/options", headers=outsider.headers)
    assert resp.status_code == 404
