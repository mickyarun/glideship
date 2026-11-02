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

"""Linked repositories at their edges: inactive repos, other orgs, archived boards, paging."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.models.tracked_repository import RepoStatus, TrackedRepository
from app.services import event_bus
from tests.integration.board_api_support import (
    BOARDS,
    link_repo,
    make_board,
    make_card,
    ok,
    page,
    person,
    tracked_repo,
    walk,
)
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration

NOT_LINKED = "Pick one of the repositories this board links."


async def _set_status(factory: Factory, repo: uuid.UUID, status: RepoStatus) -> None:
    async with factory() as db:
        await db.execute(
            update(TrackedRepository).where(TrackedRepository.id == repo).values(status=status)
        )
        await db.commit()


async def test_a_linked_repo_that_goes_inactive_is_hidden_refused_and_still_unlinkable(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    factory = pg_session_factory
    org = await new_org(factory)
    admin = await person(factory, org, "pm")
    key = (await make_board(client, admin))["board"]["key"]
    repo = await tracked_repo(factory, org)
    await link_repo(client, admin, key, repo)
    card = await make_card(client, admin, key)
    await _set_status(factory, repo, RepoStatus.REMOVED)
    assert ok(await client.get(f"{BOARDS}/{key}/repos", headers=admin.headers)) == {"items": []}
    url = f"{BOARDS}/{key}/repos/{repo}"
    assert (await client.get(url, headers=admin.headers)).status_code == 404
    named = {"title": "x", "repo_id": str(repo)}
    created = await client.post(f"{BOARDS}/{key}/cards", json=named, headers=admin.headers)
    patched = await client.patch(
        f"{BOARDS}/{key}/cards/{card['number']}",
        json={"repo_id": str(repo)},
        headers=admin.headers,
    )
    assert [r.json()["detail"] for r in (created, patched)] == [NOT_LINKED, NOT_LINKED]
    assert ok(await client.delete(url, headers=admin.headers)) == {"items": []}


async def test_ignoring_a_repo_in_settings_unlinks_it_from_every_board(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    factory = pg_session_factory
    org = await new_org(factory)
    owner = await person(factory, org, "admin")
    boards = [(await make_board(client, owner))["board"] for _ in range(2)]
    repo = await tracked_repo(factory, org)
    for board in boards:
        await link_repo(client, owner, board["key"], repo)
    card = await make_card(client, owner, boards[0]["key"], repo_id=str(repo))
    queues = {b["id"]: event_bus.subscribe(f"board:{b['id']}") for b in boards}
    try:
        url = f"/api/v1/settings/repos/{repo}/status"
        ok(await client.patch(url, json={"status": "ignored"}, headers=owner.headers))
        await asyncio.sleep(0)
        heard = {
            bid: [q.get_nowait()["data"] for _ in range(q.qsize())] for bid, q in queues.items()
        }
    finally:
        for bid, q in queues.items():
            event_bus.unsubscribe(f"board:{bid}", q)
    cleared = {
        bid: [(e["event"], e["linked"], e["cleared"]) for e in got] for bid, got in heard.items()
    }
    assert cleared == {
        boards[0]["id"]: [("repos_changed", False, 1)],
        boards[1]["id"]: [("repos_changed", False, 0)],
    }
    got = ok(
        await client.get(
            f"{BOARDS}/{boards[0]['key']}/cards/{card['number']}", headers=owner.headers
        )
    )
    assert got["repo_id"] is None
    ok(await client.patch(url, json={"status": "active"}, headers=owner.headers))
    listed = ok(await client.get(f"{BOARDS}/{boards[1]['key']}/repos", headers=owner.headers))
    assert listed == {"items": []}


async def test_other_orgs_and_people_without_a_role_learn_nothing(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    factory = pg_session_factory
    org, other = await new_org(factory), await new_org(factory)
    admin, outsider = await person(factory, org, "pm"), await person(factory, org)
    foreigner = await person(factory, other, "admin")
    key = (await make_board(client, admin, visibility="members"))["board"]["key"]
    repo, theirs = await tracked_repo(factory, org), await tracked_repo(factory, other)
    await link_repo(client, admin, key, repo)
    for who in (foreigner, outsider):
        for path in ("repos", f"repos/{repo}", "people"):
            resp = await client.get(f"{BOARDS}/{key}/{path}", headers=who.headers)
            assert resp.status_code == 404, (path, resp.text)
    card = await make_card(client, admin, key)
    named = {"title": "x", "repo_id": str(theirs)}
    created = await client.post(f"{BOARDS}/{key}/cards", json=named, headers=admin.headers)
    patched = await client.patch(
        f"{BOARDS}/{key}/cards/{card['number']}",
        json={"repo_id": str(theirs)},
        headers=admin.headers,
    )
    assert [r.json()["detail"] for r in (created, patched)] == [NOT_LINKED, NOT_LINKED]
    assert (await page(client, admin, key, card["stage_id"], repo=str(theirs)))["items"] == []


async def test_an_archived_board_refuses_link_changes(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    factory = pg_session_factory
    org = await new_org(factory)
    admin = await person(factory, org, "pm")
    key = (await make_board(client, admin))["board"]["key"]
    linked, spare = await tracked_repo(factory, org), await tracked_repo(factory, org)
    await link_repo(client, admin, key, linked)
    ok(await client.post(f"{BOARDS}/{key}/archive", headers=admin.headers))
    for method, repo in (("PUT", spare), ("DELETE", linked)):
        resp = await client.request(method, f"{BOARDS}/{key}/repos/{repo}", headers=admin.headers)
        assert resp.status_code == 409, (method, resp.text)


async def test_the_repo_filter_pages_with_a_cursor_and_checks_its_id(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    factory = pg_session_factory
    org = await new_org(factory)
    admin = await person(factory, org, "pm")
    key = (await make_board(client, admin))["board"]["key"]
    repo = await tracked_repo(factory, org)
    await link_repo(client, admin, key, repo)
    named = [await make_card(client, admin, key, f"R{i}", repo_id=str(repo)) for i in range(5)]
    await make_card(client, admin, key, "Plain")
    stage = named[0]["stage_id"]
    cards, pages = await walk(client, admin, key, stage, repo=str(repo), limit=2)
    assert [c["id"] for c in cards] == [c["id"] for c in named] and pages == 3
    bad = await client.get(
        f"{BOARDS}/{key}/cards", params={"stage_id": stage, "repo": "nope"}, headers=admin.headers
    )
    assert bad.status_code == 422
