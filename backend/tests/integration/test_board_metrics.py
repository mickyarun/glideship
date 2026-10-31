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


"""Board metrics from the cards' frozen stage categories, for one board and across boards."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import event, update

from app.models.board_card import BoardCard
from app.models.board_card_detail import BoardCardEvent
from app.models.board_enums import BoardCardEventType, BoardStageCategory
from tests.integration.board_api_support import (
    BOARDS,
    Person,
    make_board,
    make_card,
    ok,
    org_of,
    person,
    stage_id,
)
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration

NOW = datetime.now(UTC)


async def _move(
    client: AsyncClient, who: Person, key: str, card: dict[str, Any], stage: str
) -> None:
    url = f"{BOARDS}/{key}/cards/{card['number']}/move"
    ok(await client.post(url, json={"stage_id": stage}, headers=who.headers))


async def _backdate(
    factory: Factory, card: dict[str, Any], category: BoardStageCategory, at: datetime
) -> None:
    """Put the card's events into ``category`` at ``at``."""
    async with factory() as db:
        await db.execute(
            update(BoardCardEvent)
            .where(
                BoardCardEvent.card_id == uuid.UUID(card["id"]),
                BoardCardEvent.to_category == category,
            )
            .values(created_at=at)
        )
        await db.commit()


async def _delivered(factory: Factory, card: dict[str, Any], created: datetime) -> None:
    """A BUD of the card was delivered now; the card was created at ``created``."""
    card_id = uuid.UUID(card["id"])
    async with factory() as db:
        row = await db.get(BoardCard, card_id)
        assert row is not None
        row.created_at = created
        db.add(
            BoardCardEvent(
                org_id=row.org_id,
                card_id=card_id,
                board_id=row.board_id,
                type=BoardCardEventType.DELIVERED,
                detail={"bud_key": "BUD-001"},
            )
        )
        await db.commit()


async def _ops_board(
    client: AsyncClient, factory: Factory, **body: Any
) -> tuple[Person, dict[str, Any]]:
    org = await new_org(factory)
    pm = await person(factory, org, "pm")
    return pm, await make_board(client, pm, **body)


async def test_one_boards_numbers(client: AsyncClient, pg_session_factory: Factory) -> None:
    pm, board = await _ops_board(client, pg_session_factory)
    key = board["board"]["key"]
    shipped = await make_card(client, pm, key, "Shipped")
    stuck = await make_card(client, pm, key, "Stuck")
    await make_card(client, pm, key, "Waiting")
    for stage in ("In progress", "Done"):
        await _move(client, pm, key, shipped, stage_id(board, stage))
    await _move(client, pm, key, stuck, stage_id(board, "In progress"))
    done_at = NOW - timedelta(days=1)
    for card in (shipped, stuck):
        await _backdate(
            pg_session_factory, card, BoardStageCategory.TODO, NOW - timedelta(days=30)
        )
    await _backdate(
        pg_session_factory, shipped, BoardStageCategory.IN_PROGRESS, NOW - timedelta(days=3)
    )
    await _backdate(pg_session_factory, shipped, BoardStageCategory.DONE, done_at)
    await _backdate(
        pg_session_factory, stuck, BoardStageCategory.IN_PROGRESS, NOW - timedelta(days=20)
    )
    await _delivered(pg_session_factory, shipped, NOW - timedelta(days=10))

    got = ok(await client.get(f"{BOARDS}/{key}/metrics", headers=pm.headers))

    assert got["wip"] == {"todo": 1, "in_progress": 1, "done": 1, "canceled": 0}
    assert got["cycle_time"] == {"count": 1, "median_hours": 48.0, "p85_hours": 48.0}
    assert got["lead_time"]["count"] == 1 and round(got["lead_time"]["median_hours"]) == 240
    weeks = got["throughput"]
    assert len(weeks) == got["window"]["weeks"] == 12
    monday = (done_at.date() - timedelta(days=done_at.weekday())).isoformat()
    assert [w["count"] for w in weeks if w["week_start"] == monday] == [1]
    assert sum(w["count"] for w in weeks) == 1
    assert got["aging_count"] == 1
    assert [(a["key"], a["title"]) for a in got["aging"]] == [(stuck["key"], "Stuck")]


@contextmanager
def _statements(factory: Factory) -> Iterator[list[str]]:
    seen: list[str] = []
    engine = factory.kw["bind"].sync_engine

    def _count(*args: Any) -> None:
        seen.append(str(args[2]))

    event.listen(engine, "before_cursor_execute", _count)
    try:
        yield seen
    finally:
        event.remove(engine, "before_cursor_execute", _count)


async def test_the_summary_covers_the_boards_i_see_in_the_same_queries(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    pm, first = await _ops_board(client, pg_session_factory)
    org_member = await person(pg_session_factory, await org_of(pg_session_factory, pm))
    hidden = await make_board(client, pm, visibility="members")
    first_key = first["board"]["key"]
    card = await make_card(client, pm, first_key, "One")
    await _move(client, pm, first_key, card, stage_id(first, "Done"))

    with _statements(pg_session_factory) as one_board:
        mine = ok(await client.get(f"{BOARDS}/metrics/summary", headers=org_member.headers))
    assert [b["key"] for b in mine["boards"]] == [first_key]
    assert mine["boards"][0]["wip"]["done"] == 1
    assert sum(w["count"] for w in mine["boards"][0]["throughput"]) == 1

    second = await make_board(client, pm)
    with _statements(pg_session_factory) as three_boards:
        everything = ok(await client.get(f"{BOARDS}/metrics/summary", headers=pm.headers))
    keys = {b["key"] for b in everything["boards"]}
    assert keys == {first_key, hidden["board"]["key"], second["board"]["key"]}
    assert len(three_boards) == len(one_board)
    hidden_url = f"{BOARDS}/{hidden['board']['key']}/metrics"
    assert (await client.get(hidden_url, headers=org_member.headers)).status_code == 404
