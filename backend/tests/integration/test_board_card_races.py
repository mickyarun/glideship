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

"""Moves and creates racing each other: stale neighbours, respacing, numbering, keys."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.config import settings
from app.models.board_card import BoardCard
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
from tests.integration.board_support import board_key
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration


async def _setup(client: AsyncClient, factory: Factory) -> tuple[Person, dict[str, Any], str]:
    org = await new_org(factory)
    pm = await person(factory, org, "pm")
    board = await make_board(client, pm, template="ops")
    return pm, board, board["board"]["key"]


def _move(client: AsyncClient, who: Person, key: str, number: int, **body: Any) -> Any:
    return client.post(f"{BOARDS}/{key}/cards/{number}/move", json=body, headers=who.headers)


async def test_a_neighbour_that_moved_away_is_a_conflict(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    pm, board, key = await _setup(client, pg_session_factory)
    todo, done = stage_id(board, "To do"), stage_id(board, "Done")
    a, b = [await make_card(client, pm, key, t, stage_id=todo) for t in "AB"]
    ok(await _move(client, pm, key, a["number"], stage_id=done))
    stale = await _move(client, pm, key, b["number"], stage_id=todo, after_id=a["id"])
    assert stale.status_code == 409
    ok(await client.post(f"{BOARDS}/{key}/cards/{a['number']}/archive", headers=pm.headers))
    archived = await _move(client, pm, key, b["number"], stage_id=done, before_id=a["id"])
    assert archived.status_code == 409


async def test_concurrent_moves_that_force_a_respacing_all_land(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    pm, board, key = await _setup(client, pg_session_factory)
    todo, doing = stage_id(board, "To do"), stage_id(board, "In progress")
    top, bottom = [await make_card(client, pm, key, t, stage_id=doing) for t in ("Top", "Bottom")]
    movers = [await make_card(client, pm, key, f"M{i}", stage_id=todo) for i in range(4)]
    tight = settings.boards.position_epsilon / 4
    async with pg_session_factory() as db:
        for card, position in ((top, 1.0), (bottom, 1.0 + tight)):
            await db.execute(
                update(BoardCard).where(BoardCard.id == card["id"]).values(position=position)
            )
        await db.commit()
    results = await asyncio.gather(
        *(_move(client, pm, key, m["number"], stage_id=doing, after_id=top["id"]) for m in movers)
    )
    assert [r.status_code for r in results] == [200] * len(movers)
    titles = [c["title"] for c in (await page(client, pm, key, doing))["items"]]
    assert titles[0] == "Top" and titles[-1] == "Bottom"
    assert sorted(titles[1:-1]) == ["M0", "M1", "M2", "M3"]


async def test_concurrent_creates_get_distinct_numbers(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    pm, _, key = await _setup(client, pg_session_factory)
    results = await asyncio.gather(
        *(
            client.post(f"{BOARDS}/{key}/cards", json={"title": f"C{i}"}, headers=pm.headers)
            for i in range(5)
        )
    )
    assert sorted(r.json()["number"] for r in results) == [1, 2, 3, 4, 5]


async def test_two_boards_racing_for_one_key_never_both_win(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    key = board_key()
    results = await asyncio.gather(
        *(
            client.post(
                BOARDS,
                json={"name": f"Race {i}", "key": key, "template": "blank"},
                headers=pm.headers,
            )
            for i in range(2)
        )
    )
    codes = sorted(r.status_code for r in results)
    assert codes in ([201, 409], [409, 409])
    assert all(r.status_code != 500 for r in results)
