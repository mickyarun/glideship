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

"""Everyone who can open a board: the same people its cards can be assigned to."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.models.user import User
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
from tests.integration.leave_support import give_custom_role
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration


async def _people(client: AsyncClient, who: Person, key: str) -> dict[str, dict[str, Any]]:
    body = ok(await client.get(f"{BOARDS}/{key}/people", headers=who.headers))
    return {item["id"]: item for item in body["items"]}


async def _put_team(
    client: AsyncClient, admin: Person, key: str, team: uuid.UUID, role: str
) -> None:
    url = f"{BOARDS}/{key}/teams/{team}"
    ok(await client.put(url, json={"role": role}, headers=admin.headers))


async def _deactivate(factory: Factory, user: uuid.UUID) -> None:
    async with factory() as db:
        await db.execute(update(User).where(User.id == user).values(is_active=False))
        await db.commit()


async def test_a_members_only_board_lists_members_and_expanded_teams_with_the_highest_role(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    factory = pg_session_factory
    org = await new_org(factory)
    admin = await person(factory, org, "pm")
    own, teammate, both, gone, outsider = [await person(factory, org) for _ in range(5)]
    manager = await person(factory, org, "admin")
    key = (await make_board(client, admin, visibility="members"))["board"]["key"]
    await put_role(client, admin, key, own.id, "viewer")
    await put_role(client, admin, key, both.id, "viewer")
    await put_role(client, admin, key, gone.id, "editor")
    team = await new_team(factory, org, teammate.id, both.id)
    await _put_team(client, admin, key, team, "editor")
    await _deactivate(factory, gone.id)

    people = await _people(client, own, key)
    assert {uid: (p["role"], p["via"]) for uid, p in people.items()} == {
        str(admin.id): ("admin", "member"),
        str(own.id): ("viewer", "member"),
        str(teammate.id): ("editor", "team"),
        str(both.id): ("editor", "team"),
        str(manager.id): ("admin", "org"),
    }
    assert str(outsider.id) not in people and str(gone.id) not in people
    assert set(people[str(own.id)]) == {"id", "name", "avatar_url", "role", "via"}


async def test_an_org_board_lists_every_active_member_who_holds_boards_view(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    factory = pg_session_factory
    org = await new_org(factory)
    admin = await person(factory, org, "pm")
    sales, gone, no_boards = [await person(factory, org, "sales") for _ in range(3)]
    await give_custom_role(factory, org, no_boards.id, "buds:view")
    await _deactivate(factory, gone.id)
    key = (await make_board(client, admin))["board"]["key"]
    await put_role(client, admin, key, sales.id, "editor")

    people = await _people(client, sales, key)
    assert people[str(admin.id)]["role"] == "admin"
    assert (people[str(sales.id)]["role"], people[str(sales.id)]["via"]) == ("editor", "member")
    assert str(gone.id) not in people and str(no_boards.id) not in people
    others = [p for uid, p in people.items() if uid not in {str(admin.id), str(sales.id)}]
    assert all((p["role"], p["via"]) == ("viewer", "org") for p in others)
    names = [p["name"].lower() for p in people.values()]
    assert names == sorted(names)


async def test_assignees_are_exactly_the_people_listed(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    factory = pg_session_factory
    org = await new_org(factory)
    admin = await person(factory, org, "pm")
    teammate, outsider = [await person(factory, org) for _ in range(2)]
    key = (await make_board(client, admin, visibility="members"))["board"]["key"]
    await _put_team(client, admin, key, await new_team(factory, org, teammate.id), "viewer")
    listed = set(await _people(client, admin, key))
    assert listed == {str(admin.id), str(teammate.id)}
    for uid in listed:
        await make_card(client, admin, key, assignee_ids=[uid])
    url = f"{BOARDS}/{key}/cards"
    body = {"title": "x", "assignee_ids": [str(outsider.id)]}
    assert (await client.post(url, json=body, headers=admin.headers)).status_code == 422


async def test_the_people_of_a_board_stay_inside_its_org(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    factory = pg_session_factory
    org, other = await new_org(factory), await new_org(factory)
    admin = await person(factory, org, "pm")
    foreigner = await person(factory, other, "admin")
    key = (await make_board(client, admin))["board"]["key"]
    resp = await client.get(f"{BOARDS}/{key}/people", headers=foreigner.headers)
    assert resp.status_code == 404
    assert str(foreigner.id) not in await _people(client, admin, key)
