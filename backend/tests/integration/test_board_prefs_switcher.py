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

"""Stars, saved filters, last visits and the board switcher."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.config import settings
from app.models.board_member import BoardUserPrefs
from app.services.boards.constants import ID_LIST_MAX_ITEMS
from tests.integration.board_api_support import (
    BOARDS,
    link_repo,
    make_board,
    ok,
    person,
    tracked_repo,
)
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration

SWITCHER = f"{BOARDS}/switcher"


async def _opened_at(factory: Factory, board_id: str, user: uuid.UUID) -> object:
    async with factory() as db:
        return await db.scalar(
            select(BoardUserPrefs.last_opened_at).where(
                BoardUserPrefs.board_id == uuid.UUID(board_id), BoardUserPrefs.user_id == user
            )
        )


async def test_stars_and_filters_are_saved_per_person(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    viewer = await person(pg_session_factory, org, "sales")
    key = (await make_board(client, pm))["board"]["key"]
    url = f"{BOARDS}/{key}"
    starred = ok(await client.put(f"{url}/star", json={"starred": True}, headers=viewer.headers))
    assert starred["starred"] is True
    filters = {"q": "seo", "priorities": ["P0"], "archived": True}
    saved = ok(await client.put(f"{url}/prefs", json=filters, headers=viewer.headers))
    assert saved["filters"]["q"] == "seo" and saved["filters"]["priorities"] == ["P0"]
    assert ok(await client.get(f"{url}/prefs", headers=pm.headers)) == {
        "starred": False,
        "filters": {
            "q": None,
            "assignee_ids": [],
            "label_ids": [],
            "priorities": [],
            "repo_ids": [],
            "archived": False,
        },
    }
    assert ok(await client.get(url, headers=viewer.headers))["starred"] is True


async def test_saved_filters_are_capped(client: AsyncClient, pg_session_factory: Factory) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    url = f"{BOARDS}/{(await make_board(client, pm))['board']['key']}/prefs"
    many = [str(uuid.uuid4()) for _ in range(settings.boards.filters_max_bytes // 36 + 1)]
    resp = await client.put(url, json={"label_ids": many}, headers=pm.headers)
    assert resp.status_code == 422
    unknown = await client.put(url, json={"colour": "red"}, headers=pm.headers)
    assert unknown.status_code == 422


async def test_the_repository_filter_keeps_only_repositories_the_board_links(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    factory = pg_session_factory
    org = await new_org(factory)
    pm = await person(factory, org, "pm")
    key = (await make_board(client, pm))["board"]["key"]
    url = f"{BOARDS}/{key}"
    kept, unlinked = await tracked_repo(factory, org), await tracked_repo(factory, org)
    foreign = await tracked_repo(factory, await new_org(factory))
    await link_repo(client, pm, key, kept)
    await link_repo(client, pm, key, unlinked)
    body = {"repo_ids": [str(kept), str(unlinked), str(foreign)]}
    saved = ok(await client.put(f"{url}/prefs", json=body, headers=pm.headers))
    assert saved["filters"]["repo_ids"] == [str(kept), str(unlinked)]

    ok(await client.delete(f"{url}/repos/{unlinked}", headers=pm.headers))
    assert ok(await client.get(f"{url}/prefs", headers=pm.headers))["filters"]["repo_ids"] == [
        str(kept)
    ]
    assert ok(await client.get(url, headers=pm.headers))["filters"]["repo_ids"] == [str(kept)]

    many = [str(uuid.uuid4()) for _ in range(ID_LIST_MAX_ITEMS + 1)]
    resp = await client.put(f"{url}/prefs", json={"repo_ids": many}, headers=pm.headers)
    assert resp.status_code == 422


async def test_opening_a_board_records_the_visit_at_most_once_per_interval(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    board = (await make_board(client, pm))["board"]
    url = f"{BOARDS}/{board['key']}"
    ok(await client.get(url, headers=pm.headers))
    first = await _opened_at(pg_session_factory, board["id"], pm.id)
    ok(await client.get(url, headers=pm.headers))
    assert await _opened_at(pg_session_factory, board["id"], pm.id) == first

    async with pg_session_factory() as db:
        back = timedelta(seconds=settings.boards.prefs_touch_interval_seconds + 1)
        await db.execute(
            update(BoardUserPrefs)
            .where(BoardUserPrefs.board_id == uuid.UUID(board["id"]))
            .values(last_opened_at=BoardUserPrefs.last_opened_at - back)
        )
        await db.commit()
    moved_back = await _opened_at(pg_session_factory, board["id"], pm.id)
    ok(await client.get(url, headers=pm.headers))
    assert await _opened_at(pg_session_factory, board["id"], pm.id) != moved_back


async def test_the_switcher_groups_boards_i_can_open(
    client: AsyncClient, pg_session_factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    sales = await person(pg_session_factory, org, "sales")
    names = ["Alpha", "Bravo", "Charlie", "Delta", "Echo"]
    boards = {n: (await make_board(client, pm, name=n))["board"] for n in names}
    hidden = (await make_board(client, pm, name="Hidden", visibility="members"))["board"]
    ok(
        await client.put(
            f"{BOARDS}/{boards['Echo']['key']}/star", json={"starred": True}, headers=sales.headers
        )
    )
    ok(await client.get(f"{BOARDS}/{boards['Delta']['key']}", headers=sales.headers))
    monkeypatch.setattr(settings.boards, "switcher_other_limit", 2)

    groups = ok(await client.get(SWITCHER, headers=sales.headers))
    assert [b["name"] for b in groups["starred"]] == ["Echo"]
    assert [b["name"] for b in groups["recent"]] == ["Delta"]
    assert [b["name"] for b in groups["other"]] == ["Alpha", "Bravo"]
    assert groups["delivery"] is None

    searched = ok(await client.get(SWITCHER, params={"q": "char"}, headers=sales.headers))
    assert [b["name"] for b in searched["other"]] == ["Charlie"]
    assert searched["starred"] == [] and searched["recent"] == []
    by_key = ok(
        await client.get(SWITCHER, params={"q": boards["Bravo"]["key"]}, headers=sales.headers)
    )
    assert [b["name"] for b in by_key["other"]] == ["Bravo"]
    secret = ok(await client.get(SWITCHER, params={"q": "Hidden"}, headers=sales.headers))
    assert secret["other"] == []

    mine = ok(await client.get(SWITCHER, params={"q": "Hidden"}, headers=pm.headers))
    assert [b["key"] for b in mine["other"]] == [hidden["key"]]
    assert ok(await client.get(SWITCHER, headers=pm.headers))["delivery"] == {
        "kind": "delivery",
        "name": "Delivery",
        "path": "/buds",
    }
    assert (
        ok(await client.get(SWITCHER, params={"q": "zzz"}, headers=pm.headers))["delivery"] is None
    )
