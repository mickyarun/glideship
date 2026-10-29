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
from sqlalchemy import event

from app.config import settings
from app.repositories.board_card_summary import BoardCardSummaryRepository, CardQuery
from tests.integration.board_api_support import (
    BOARDS,
    Person,
    make_board,
    make_card,
    ok,
    page,
    person,
    stage_id,
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


async def test_pages_follow_position_then_id_and_filters_narrow_them(
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
    titles = [f"Card {i:02d}" for i in range(7)]
    for i, title in enumerate(titles):
        extra = {"label_ids": [label["id"]], "priority": "P0"} if i % 3 == 0 else {}
        await make_card(client, pm, key, title, **extra)

    seen, after = [], None
    while True:
        params = {"limit": 3, **({"after": after} if after else {})}
        body = await page(client, pm, key, backlog, **params)
        seen += [c["title"] for c in body["items"]]
        after = body["next_after"]
        if after is None:
            break
    assert seen == titles

    labelled = await page(client, pm, key, backlog, label=label["id"])
    assert [c["title"] for c in labelled["items"]] == ["Card 00", "Card 03", "Card 06"]
    assert [
        c["title"] for c in (await page(client, pm, key, backlog, priority="P0"))["items"]
    ] == [
        "Card 00",
        "Card 03",
        "Card 06",
    ]
    assert [c["title"] for c in (await page(client, pm, key, backlog, q="d 04"))["items"]] == [
        "Card 04"
    ]
    over = await client.get(
        f"{BOARDS}/{key}/cards",
        params={"stage_id": backlog, "limit": settings.boards.stage_page_size + 1},
        headers=pm.headers,
    )
    assert over.status_code == 422
    other_stage = await client.get(
        f"{BOARDS}/{key}/cards", params={"stage_id": str(uuid.uuid4())}, headers=pm.headers
    )
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
        card = await make_card(client, pm, key, f"C{i}", label_ids=[label["id"]])
        ok(
            await client.post(
                f"{BOARDS}/{key}/cards/{card['number']}/checklist",
                json={"text": "step"},
                headers=pm.headers,
            ),
            201,
        )

    async with pg_session_factory() as db:
        repo = BoardCardSummaryRepository(db, org_id=await _org_of(client, pm))
        query = CardQuery(stage_id=uuid.UUID(backlog), limit=50)
        with _count_statements(pg_session_factory) as seen:
            rows = await repo.list_summaries(uuid.UUID(board["board"]["id"]), query)
    assert len(rows) == 12 and len(seen) == 1
    assert all(r.label_ids == [uuid.UUID(label["id"])] for r in rows)
    assert all((r.checklist_done, r.checklist_total) == (0, 1) for r in rows)

    with _count_statements(pg_session_factory) as small:
        await page(client, pm, key, backlog, limit=2)
    with _count_statements(pg_session_factory) as large:
        await page(client, pm, key, backlog, limit=12)
    assert len(small) == len(large)
