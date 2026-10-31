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

"""Helpers for the boards API tests: people, boards and cards made through HTTP."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.permission import Permission
from app.models.role import Role, RolePermission, RoleScopeType
from app.models.tracked_repository import RepoStatus, TrackedRepository
from app.models.user import OrgToUser
from app.services.boards import attachment_links, attachment_service
from app.services.file_storage import FileStorage
from tests.integration.board_support import board_key
from tests.integration.scan_features_bugs_support import Factory, as_user, new_member, new_org

BOARDS = "/api/v1/boards"


@dataclass(frozen=True)
class Person:
    """A member and the headers that sign them in."""

    id: uuid.UUID
    headers: dict[str, str]


async def person(factory: Factory, org: uuid.UUID, role: str | None = "developer") -> Person:
    """A new member of ``org`` holding the system role ``role``."""
    user = await new_member(factory, org, role)
    return Person(user, as_user(user, org))


def ok(resp: Any, code: int = 200) -> Any:
    """The JSON body, after checking the status."""
    assert resp.status_code == code, resp.text
    return resp.json() if resp.content else None


async def make_board(
    client: AsyncClient, who: Person, *, template: str = "ops", **body: Any
) -> dict[str, Any]:
    """A board made through the API by ``who`` (who becomes its admin)."""
    payload = {"name": f"Board {uuid.uuid4().hex[:6]}", "key": board_key(), "template": template}
    return ok(await client.post(BOARDS, json={**payload, **body}, headers=who.headers), 201)


def stage_id(board: dict[str, Any], name: str) -> str:
    """The id of the board's stage called ``name``."""
    return next(s["id"] for s in board["stages"] if s["name"] == name)


async def make_card(
    client: AsyncClient, who: Person, key: str, title: str = "Card", **body: Any
) -> dict[str, Any]:
    """A card made through the API."""
    url = f"{BOARDS}/{key}/cards"
    return ok(await client.post(url, json={"title": title, **body}, headers=who.headers), 201)


async def put_role(
    client: AsyncClient, admin: Person, key: str, user: uuid.UUID, role: str
) -> dict[str, Any]:
    """Give ``user`` their own role on the board."""
    url = f"{BOARDS}/{key}/members/{user}"
    return ok(await client.put(url, json={"role": role}, headers=admin.headers))


async def page(
    client: AsyncClient, who: Person, key: str, stage: str | None, **params: Any
) -> dict[str, Any]:
    """One page of a stage's cards (the whole board's when ``stage`` is None)."""
    url = f"{BOARDS}/{key}/cards"
    query = {**({"stage_id": stage} if stage else {}), **params}
    return ok(await client.get(url, params=query, headers=who.headers))


async def walk(
    client: AsyncClient, who: Person, key: str, stage: str | None, **params: Any
) -> tuple[list[dict[str, Any]], int]:
    """Every card across all pages, and how many pages it took."""
    cards, cursor, pages = [], None, 0
    while True:
        body = await page(
            client, who, key, stage, **params, **({"cursor": cursor} if cursor else {})
        )
        cards += body["items"]
        pages += 1
        cursor = body["next_cursor"]
        if cursor is None:
            return cards, pages


async def custom_role(factory: Factory, org: uuid.UUID, *permissions: str) -> uuid.UUID:
    """A custom role in ``org`` holding exactly ``permissions``, assigned to nobody."""
    async with factory() as db:
        role = Role(
            name=f"custom-{uuid.uuid4().hex[:8]}", org_id=org, scope_type=RoleScopeType.CUSTOM
        )
        db.add(role)
        await db.flush()
        found = await db.scalars(select(Permission).where(Permission.resource_id.in_(permissions)))
        db.add_all(RolePermission(role_id=role.id, permission_id=p.id) for p in found)
        await db.commit()
        return role.id


@dataclass(frozen=True)
class CardTeam:
    """An admin, an editor and a viewer on a members-only board, and one card's url."""

    admin: Person
    editor: Person
    viewer: Person
    key: str
    url: str


async def card_team(client: AsyncClient, factory: Factory) -> CardTeam:
    """A new org with a members-only board, three people on it and one card."""
    org = await new_org(factory)
    admin = await person(factory, org, "pm")
    editor, viewer = [await person(factory, org) for _ in range(2)]
    key = (await make_board(client, admin, visibility="members"))["board"]["key"]
    await put_role(client, admin, key, editor.id, "editor")
    await put_role(client, admin, key, viewer.id, "viewer")
    card = await make_card(client, admin, key)
    return CardTeam(admin, editor, viewer, key, f"{BOARDS}/{key}/cards/{card['number']}")


def use_local_storage(root: Path, monkeypatch: pytest.MonkeyPatch) -> FileStorage:
    """Point card attachments at a local directory."""
    storage = FileStorage()
    storage.use_s3 = False
    storage.local_dir = str(root)
    for module in (attachment_service, attachment_links):
        monkeypatch.setattr(module, "get_file_storage", lambda: storage)
    return storage


async def tracked_repo(
    factory: Factory,
    org: uuid.UUID,
    *,
    full_name: str | None = None,
    status: RepoStatus = RepoStatus.ACTIVE,
) -> uuid.UUID:
    """A tracked repository in ``org``."""
    async with factory() as db:
        name = f"repo-{uuid.uuid4().hex[:6]}"
        repo = TrackedRepository(
            org_id=org,
            path=f"/tmp/{name}",
            name=name,
            status=status,
            github_repo_full_name=full_name,
        )
        db.add(repo)
        await db.commit()
        return repo.id


async def org_of(factory: Factory, who: Person) -> uuid.UUID:
    """The org ``who`` is a member of."""
    async with factory() as db:
        org = await db.scalar(select(OrgToUser.org_id).where(OrgToUser.user_id == who.id))
        assert org is not None
        return org


async def link_repo(client: AsyncClient, admin: Person, key: str, repo: uuid.UUID) -> Any:
    """Link ``repo`` to the board; the board's linked repositories."""
    return ok(await client.put(f"{BOARDS}/{key}/repos/{repo}", headers=admin.headers))
