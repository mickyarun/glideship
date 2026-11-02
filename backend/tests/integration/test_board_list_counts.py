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

"""What the boards list and a board's page carry beyond the board itself.

Counts per category come from the list's single query; a board opens with
my saved filters; the limits include the key's length.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.config import settings
from app.core.upload_limits import MIB
from app.models.board_card import BoardCard
from app.services.boards.constants import BOARD_KEY_MAX_LENGTH, BOARD_KEY_MIN_LENGTH
from tests.integration.board_api_support import (
    BOARDS,
    make_board,
    make_card,
    ok,
    person,
    stage_id,
)
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration


async def test_the_list_counts_open_cards_and_recently_done_ones(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    board = await make_board(client, pm, template="ops", description="Infra requests")
    key = board["board"]["key"]
    cards = [await make_card(client, pm, key, f"Card {i}") for i in range(5)]
    url = f"{BOARDS}/{key}/cards"

    async def move(card: dict[str, object], stage: str) -> None:
        body = {"stage_id": stage_id(board, stage)}
        ok(await client.post(f"{url}/{card['number']}/move", json=body, headers=pm.headers))

    await move(cards[1], "In progress")
    await move(cards[2], "Done")
    await move(cards[3], "Done")
    ok(await client.post(f"{url}/{cards[4]['number']}/archive", headers=pm.headers))
    # One of the done cards finished before the window opened.
    old = datetime.now(UTC) - timedelta(days=settings.boards.recent_done_days + 1)
    async with pg_session_factory() as db:
        stmt = update(BoardCard).where(BoardCard.id == cards[3]["id"]).values(completed_at=old)
        await db.execute(stmt)
        await db.commit()

    items = ok(await client.get(BOARDS, headers=pm.headers))["items"]
    mine = next(i for i in items if i.get("key") == key)
    assert mine["counts"] == {"todo": 1, "in_progress": 1, "done_recent": 1}
    assert mine["description"] == "Infra requests"
    # The switcher shares the item shape; it counts open cards only.
    switcher = ok(await client.get(f"{BOARDS}/switcher", headers=pm.headers))
    row = next(b for group in ("recent", "other") for b in switcher[group] if b["key"] == key)
    assert row["counts"] == {"todo": 1, "in_progress": 1, "done_recent": 0}


async def test_a_board_without_cards_counts_nothing(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    key = (await make_board(client, pm))["board"]["key"]
    items = ok(await client.get(BOARDS, headers=pm.headers))["items"]
    mine = next(i for i in items if i.get("key") == key)
    assert mine["counts"] == {"todo": 0, "in_progress": 0, "done_recent": 0}


async def test_a_board_opens_with_my_saved_filters(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    key = (await make_board(client, pm))["board"]["key"]
    empty = ok(await client.get(f"{BOARDS}/{key}", headers=pm.headers))["filters"]
    assert empty == {
        "q": None,
        "assignee_ids": [],
        "label_ids": [],
        "priorities": [],
        "repo_ids": [],
        "archived": False,
    }
    saved = {"q": "seo", "priorities": ["P1"], "archived": True}
    ok(await client.put(f"{BOARDS}/{key}/prefs", json=saved, headers=pm.headers))
    filters = ok(await client.get(f"{BOARDS}/{key}", headers=pm.headers))["filters"]
    assert filters["q"] == "seo" and filters["priorities"] == ["P1"] and filters["archived"]


async def test_limits_include_the_key_length_and_the_done_window(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    limits = ok(await client.get(f"{BOARDS}/limits", headers=pm.headers))
    assert limits["board_key_min"] == BOARD_KEY_MIN_LENGTH
    assert limits["board_key_max"] == BOARD_KEY_MAX_LENGTH
    assert limits["recent_done_days"] == settings.boards.recent_done_days
    assert limits["import_max_upload_mb"] == settings.boards.import_max_upload_bytes // MIB
