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


"""A card that enters done more than once counts once, on its board and in the summary."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.models.board_card_detail import BoardCardEvent
from app.models.board_enums import BoardStageCategory
from tests.integration.board_api_support import BOARDS, make_board, make_card, ok, person, stage_id
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration


async def _backdate_first_done(factory: Factory, card: dict[str, Any], at: datetime) -> None:
    """Move the card's earliest entry into done back to ``at``."""
    async with factory() as db:
        first = (
            await db.execute(
                select(BoardCardEvent.id)
                .where(
                    BoardCardEvent.card_id == uuid.UUID(card["id"]),
                    BoardCardEvent.to_category == BoardStageCategory.DONE,
                )
                .order_by(BoardCardEvent.created_at)
                .limit(1)
            )
        ).scalar_one()
        await db.execute(
            update(BoardCardEvent).where(BoardCardEvent.id == first).values(created_at=at)
        )
        await db.commit()


def _weeks(flow: dict[str, Any]) -> dict[str, int]:
    return {w["week_start"]: w["count"] for w in flow["throughput"] if w["count"]}


async def test_done_twice_counts_once_in_the_week_it_was_last_done(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    board = await make_board(client, pm)
    key = board["board"]["key"]
    card = await make_card(client, pm, key, "Sent back")
    move = f"{BOARDS}/{key}/cards/{card['number']}/move"
    for stage in ("In progress", "Done", "In progress", "Done"):
        ok(await client.post(move, json={"stage_id": stage_id(board, stage)}, headers=pm.headers))
    # The first finish was two weeks ago; it was sent back and finished again now.
    await _backdate_first_done(pg_session_factory, card, datetime.now(UTC) - timedelta(weeks=2))

    one = ok(await client.get(f"{BOARDS}/{key}/metrics", headers=pm.headers))
    today = datetime.now(UTC).date()
    this_week = (today - timedelta(days=today.weekday())).isoformat()
    assert _weeks(one) == {this_week: 1}
    assert one["cycle_time"]["count"] == 1

    summary = ok(await client.get(f"{BOARDS}/metrics/summary", headers=pm.headers))
    (row,) = summary["boards"]
    assert row["key"] == key
    assert row["throughput"] == one["throughput"]
    assert row["cycle_time"] == one["cycle_time"]
