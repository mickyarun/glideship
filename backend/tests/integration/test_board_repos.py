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

"""Repositories a board links, and the one repository a card can name."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest
from httpx import AsyncClient

from app.models.tracked_repository import RepoStatus
from app.services import event_bus
from tests.integration.board_api_support import (
    BOARDS,
    Person,
    link_repo,
    make_board,
    make_card,
    ok,
    page,
    person,
    put_role,
    tracked_repo,
)
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration


async def _setup(
    client: AsyncClient, factory: Factory
) -> tuple[uuid.UUID, Person, Person, Person, str]:
    org = await new_org(factory)
    admin = await person(factory, org, "pm")
    editor, viewer = [await person(factory, org) for _ in range(2)]
    key = (await make_board(client, admin, visibility="members"))["board"]["key"]
    await put_role(client, admin, key, editor.id, "editor")
    await put_role(client, admin, key, viewer.id, "viewer")
    return org, admin, editor, viewer, key


async def test_admins_link_and_unlink_and_everyone_on_the_board_sees_the_links(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, admin, editor, viewer, key = await _setup(client, pg_session_factory)
    repo = await tracked_repo(pg_session_factory, org, full_name="acme/web")
    url = f"{BOARDS}/{key}/repos/{repo}"
    assert (await client.put(url, headers=editor.headers)).status_code == 403
    linked = await link_repo(client, admin, key, repo)
    assert [(r["id"], r["url"]) for r in linked["items"]] == [
        (str(repo), "https://github.com/acme/web")
    ]
    assert (await link_repo(client, admin, key, repo))["items"] == linked["items"]
    assert ok(await client.get(f"{BOARDS}/{key}/repos", headers=viewer.headers)) == linked
    assert ok(await client.get(url, headers=viewer.headers)) == linked["items"][0]
    assert (await client.delete(url, headers=editor.headers)).status_code == 403
    assert ok(await client.delete(url, headers=admin.headers)) == {"items": []}
    assert (await client.delete(url, headers=admin.headers)).status_code == 404
    assert (await client.get(url, headers=viewer.headers)).status_code == 404
    board = ok(await client.get(f"{BOARDS}/{key}", headers=admin.headers))
    assert "manage_repos" in board["capabilities"]
    mine = ok(await client.get(f"{BOARDS}/{key}", headers=editor.headers))
    assert "manage_repos" not in mine["capabilities"]


async def test_options_are_the_orgs_active_repositories_and_only_those_can_be_linked(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    factory = pg_session_factory
    org, admin, editor, _, key = await _setup(client, factory)
    active, linked = await tracked_repo(factory, org), await tracked_repo(factory, org)
    ignored = await tracked_repo(factory, org, status=RepoStatus.IGNORED)
    foreign = await tracked_repo(factory, await new_org(factory))
    await link_repo(client, admin, key, linked)
    options = ok(await client.get(f"{BOARDS}/{key}/repos/options", headers=admin.headers))
    flags = {item["id"]: item["linked"] for item in options["items"]}
    assert flags == {str(active): False, str(linked): True}
    resp = await client.get(f"{BOARDS}/{key}/repos/options", headers=editor.headers)
    assert resp.status_code == 403
    for repo in (ignored, foreign, uuid.uuid4()):
        url = f"{BOARDS}/{key}/repos/{repo}"
        assert (await client.put(url, headers=admin.headers)).status_code == 404


async def test_a_card_names_only_a_repository_its_board_links(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, admin, editor, _, key = await _setup(client, pg_session_factory)
    repo, other = [await tracked_repo(pg_session_factory, org) for _ in range(2)]
    await link_repo(client, admin, key, repo)
    cards = f"{BOARDS}/{key}/cards"
    refused = await client.post(
        cards, json={"title": "x", "repo_id": str(other)}, headers=editor.headers
    )
    assert refused.status_code == 422
    card = await make_card(client, editor, key, repo_id=str(repo))
    assert card["repo_id"] == str(repo)
    url = f"{cards}/{card['number']}"
    patch = await client.patch(url, json={"repo_id": str(other)}, headers=editor.headers)
    assert patch.status_code == 422
    assert (
        ok(await client.patch(url, json={"repo_id": None}, headers=editor.headers))["repo_id"]
        is None
    )
    again = ok(await client.patch(url, json={"repo_id": str(repo)}, headers=editor.headers))
    assert again["repo_id"] == str(repo)


async def test_unlinking_clears_the_cards_and_announces_them(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, admin, editor, viewer, key = await _setup(client, pg_session_factory)
    repo, kept = [await tracked_repo(pg_session_factory, org) for _ in range(2)]
    for linked in (repo, kept):
        await link_repo(client, admin, key, linked)
    on_repo = [await make_card(client, editor, key, f"R{i}", repo_id=str(repo)) for i in range(2)]
    on_kept = await make_card(client, editor, key, "K", repo_id=str(kept))
    plain = await make_card(client, editor, key, "P")
    stage = on_kept["stage_id"]

    filtered = await _filter(client, viewer, key, stage, repo)
    assert {c["id"] for c in filtered} == {c["id"] for c in on_repo}
    assert plain["id"] not in {c["id"] for c in await _filter(client, viewer, key, stage, kept)}

    board_id = ok(await client.get(f"{BOARDS}/{key}", headers=admin.headers))["board"]["id"]
    queue = event_bus.subscribe(f"board:{board_id}")
    try:
        ok(await client.delete(f"{BOARDS}/{key}/repos/{repo}", headers=admin.headers))
        await asyncio.sleep(0)
        events = [queue.get_nowait()["data"] for _ in range(queue.qsize())]
    finally:
        event_bus.unsubscribe(f"board:{board_id}", queue)
    assert events[0]["event"] == "repos_changed"
    assert (events[0]["repo_id"], events[0]["linked"]) == (str(repo), False)
    updated = {e["card"]["id"]: e["card"]["repo_id"] for e in events[1:]}
    assert all(e["event"] == "card_updated" for e in events[1:])
    assert updated == {c["id"]: None for c in on_repo}

    for card in on_repo:
        got = ok(
            await client.get(f"{BOARDS}/{key}/cards/{card['number']}", headers=viewer.headers)
        )
        assert got["repo_id"] is None
    still = ok(
        await client.get(f"{BOARDS}/{key}/cards/{on_kept['number']}", headers=viewer.headers)
    )
    assert still["repo_id"] == str(kept)
    assert await _filter(client, viewer, key, stage, repo) == []


async def _filter(
    client: AsyncClient, who: Person, key: str, stage: str, repo: uuid.UUID
) -> list[dict[str, Any]]:
    return list((await page(client, who, key, stage, repo=str(repo)))["items"])
