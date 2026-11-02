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

"""Paging a stage's cards: keyset order, filters, and one query per page."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import event, update

from app.config import settings
from app.models.board_card import BoardCard
from app.repositories.board_card_filters import CardQuery
from app.repositories.board_card_summary import BoardCardSummaryRepository
from tests.integration.board_api_support import (
    BOARDS,
    Person,
    make_board,
    make_card,
    ok,
    page,
    person,
    stage_id,
    walk,
)
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration


async def _setup(client: AsyncClient, factory: Factory) -> tuple[Person, dict[str, Any], str]:
    org = await new_org(factory)
    pm = await person(factory, org, "pm")
    board = await make_board(client, pm, template="ops")
    return pm, board, board["board"]["key"]


async def _org_of(client: AsyncClient, who: Person) -> uuid.UUID:
    return uuid.UUID(ok(await client.get("/api/v1/auth/me", headers=who.headers))["org_id"])


async def _label(client: AsyncClient, pm: Person, key: str) -> str:
    url = f"{BOARDS}/{key}/labels"
    body = ok(await client.post(url, json={"name": "L", "color": "red"}, headers=pm.headers), 201)
    return str(body["id"])


async def test_pages_follow_position_and_filters_narrow_them(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    pm, board, key = await _setup(client, pg_session_factory)
    backlog = stage_id(board, "Backlog")
    label = await _label(client, pm, key)
    titles = [f"Card {i:02d}" for i in range(7)]
    for i, title in enumerate(titles):
        extra = {"label_ids": [label], "priority": "P0"} if i % 3 == 0 else {}
        await make_card(client, pm, key, title, **extra)

    cards, pages = await walk(client, pm, key, backlog, limit=3)
    assert [c["title"] for c in cards] == titles and pages == 3
    tagged = ["Card 00", "Card 03", "Card 06"]
    cards, pages = await walk(client, pm, key, backlog, label=label, limit=2)
    assert [c["title"] for c in cards] == tagged and pages == 2
    cards, _ = await walk(client, pm, key, backlog, priority="P0")
    assert [c["title"] for c in cards] == tagged
    found = await page(client, pm, key, backlog, q="d 04")
    assert [c["title"] for c in found["items"]] == ["Card 04"]


async def test_an_exact_last_page_has_no_next_cursor(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    pm, board, key = await _setup(client, pg_session_factory)
    backlog = stage_id(board, "Backlog")
    for i in range(4):
        await make_card(client, pm, key, f"C{i}")
    first = await page(client, pm, key, backlog, limit=2)
    second = await page(client, pm, key, backlog, limit=2, cursor=first["next_cursor"])
    assert len(second["items"]) == 2 and second["next_cursor"] is None


async def test_tied_positions_page_every_card_once_in_id_order(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    pm, board, key = await _setup(client, pg_session_factory)
    backlog = stage_id(board, "Backlog")
    made = [await make_card(client, pm, key, f"Tie {i}") for i in range(5)]
    async with pg_session_factory() as db:
        await db.execute(
            update(BoardCard)
            .where(BoardCard.id.in_([uuid.UUID(c["id"]) for c in made]))
            .values(position=1.0)
        )
        await db.commit()
    cards, pages = await walk(client, pm, key, backlog, limit=2)
    assert [c["id"] for c in cards] == sorted(c["id"] for c in made) and pages == 3


async def test_board_wide_lists_need_a_search_or_the_archive(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    pm, board, key = await _setup(client, pg_session_factory)
    await make_card(client, pm, key, "Backlog needle")
    await make_card(client, pm, key, "Doing needle", stage_id=stage_id(board, "In progress"))
    await make_card(client, pm, key, "Other")
    cards, _ = await walk(client, pm, key, None, q="needle")
    assert sorted(c["title"] for c in cards) == ["Backlog needle", "Doing needle"]
    url = f"{BOARDS}/{key}/cards"
    assert (await client.get(url, headers=pm.headers)).status_code == 422
    bad = await client.get(url, params={"q": "x", "cursor": "nope"}, headers=pm.headers)
    assert bad.status_code == 422
    over = await client.get(
        url,
        params={"q": "x", "limit": settings.boards.stage_page_size + 1},
        headers=pm.headers,
    )
    assert over.status_code == 422
    other_stage = await client.get(url, params={"stage_id": str(uuid.uuid4())}, headers=pm.headers)
    assert other_stage.status_code == 404


@contextmanager
def _count_statements(factory: Factory) -> Iterator[list[str]]:
    engine = factory.kw["bind"].sync_engine
    seen: list[str] = []

    def _record(*args: Any) -> None:
        seen.append(args[2])

    event.listen(engine, "before_cursor_execute", _record)
    try:
        yield seen
    finally:
        event.remove(engine, "before_cursor_execute", _record)


async def test_a_page_is_one_query_however_many_cards_it_holds(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    pm, board, key = await _setup(client, pg_session_factory)
    backlog = stage_id(board, "Backlog")
    label = ok(
        await client.post(
            f"{BOARDS}/{key}/labels", json={"name": "L", "color": "red"}, headers=pm.headers
        ),
        201,
    )
    for i in range(12):
        described = {"description_md": "Why"} if i % 2 else {"description_md": " \n "}
        card = await make_card(client, pm, key, f"C{i}", label_ids=[label["id"]], **described)
        card_url = f"{BOARDS}/{key}/cards/{card['number']}"
        ok(
            await client.post(f"{card_url}/checklist", json={"text": "step"}, headers=pm.headers),
            201,
        )
        if i % 3 == 0 and i % 2:
            body = {"body_md": "The PRD", "base_version": None}
            ok(await client.put(f"{card_url}/docs/prd", json=body, headers=pm.headers))

    async with pg_session_factory() as db:
        repo = BoardCardSummaryRepository(db, org_id=await _org_of(client, pm))
        query = CardQuery(stage_id=uuid.UUID(backlog), limit=50)
        with _count_statements(pg_session_factory) as seen:
            rows = await repo.list_summaries(uuid.UUID(board["board"]["id"]), query)
    assert len(rows) == 12 and len(seen) == 1
    assert all(r.label_ids == [uuid.UUID(label["id"])] for r in rows)
    assert all((r.checklist_done, r.checklist_total) == (0, 1) for r in rows)
    by_title = {r.title: r for r in rows}
    for i in range(12):
        row = by_title[f"C{i}"]
        assert row.has_description is bool(i % 2), i
        assert row.has_prd is (i % 3 == 0 and bool(i % 2)), i
        assert row.repo_id is None

    with _count_statements(pg_session_factory) as small:
        await page(client, pm, key, backlog, limit=2)
    with _count_statements(pg_session_factory) as large:
        await page(client, pm, key, backlog, limit=12)
    assert len(small) == len(large)
