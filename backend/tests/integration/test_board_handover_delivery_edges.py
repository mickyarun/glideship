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

"""A failing delivered hook, chips refreshing on a status change, two BUDs shipping at once."""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.board_enums import BoardCardEventType
from app.models.bud import BUDStatus
from app.models.developer_xp import RewardEvent
from tests.integration.board_api_support import ok
from tests.integration.board_handover_return_support import (
    BUDS,
    board_events,
    bud_of,
    card_events,
    handed,
    set_status,
)
from tests.integration.board_handover_support import card, desk, stubbed
from tests.integration.board_notify_support import fake_slack
from tests.integration.bud_lifecycle_reads import load_bud
from tests.integration.bud_lifecycle_support import (
    app_database_blocked as app_database_blocked,
)
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _slack(monkeypatch: pytest.MonkeyPatch, pg_session_factory: Factory) -> None:
    fake_slack(monkeypatch, pg_session_factory)


async def test_a_failing_delivered_hook_still_ships_the_bud(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """The hook raises in its SAVEPOINT: prod and the completion XP still commit."""
    d = await desk(client, pg_session_factory)
    made = await handed(client, d.pm, await card(client, d, description_md="x"))
    bud_id = bud_of(made)
    await set_status(pg_session_factory, bud_id, BUDStatus.UAT)
    broken = AsyncMock(side_effect=RuntimeError("board down"))
    with stubbed(), patch("app.services.bud_closure.notify_origin_card", broken):
        res = await client.patch(f"{BUDS}/{bud_id}", json={"status": "prod"}, headers=d.pm.headers)
    assert res.status_code == 200, res.text
    broken.assert_awaited_once()
    assert (await load_bud(pg_session_factory, bud_id)).status is BUDStatus.PROD
    async with pg_session_factory() as db:
        sources = set(
            await db.scalars(select(RewardEvent.source).where(RewardEvent.org_id == d.org))
        )
    assert "bud_completed" in sources
    assert (
        await card_events(pg_session_factory, made["card"]["id"], BoardCardEventType.DELIVERED)
        == []
    )


async def test_a_status_change_refreshes_the_cards_chips(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """``card_handovers_changed {card_id}`` reaches the board after the PATCH commits."""
    d = await desk(client, pg_session_factory)
    made = await handed(client, d.pm, await card(client, d, description_md="x"))
    async with board_events(d) as events:
        with stubbed():
            ok(
                await client.patch(
                    f"{BUDS}/{bud_of(made)}", json={"status": "design"}, headers=d.pm.headers
                )
            )
    changed = [e for e in events if e["event"] == "card_handovers_changed"]
    assert changed and {e["card_id"] for e in changed} == {made["card"]["id"]}


async def test_two_buds_shipping_at_once_deliver_the_card_once(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """The card lock serialises the hooks: two delivered events, one fully delivered."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="x")
    first, second = await handed(client, d.pm, url), await handed(client, d.pm, url)
    ids: list[uuid.UUID] = [bud_of(first), bud_of(second)]
    for bud_id in ids:
        await set_status(pg_session_factory, bud_id, BUDStatus.UAT)
    with stubbed():
        results = await asyncio.gather(
            *(
                client.patch(f"{BUDS}/{bud_id}", json={"status": "prod"}, headers=d.pm.headers)
                for bud_id in ids
            )
        )
    assert [r.status_code for r in results] == [200, 200]
    card_id = first["card"]["id"]
    assert len(await card_events(pg_session_factory, card_id, BoardCardEventType.DELIVERED)) == 2
    assert (
        len(await card_events(pg_session_factory, card_id, BoardCardEventType.FULLY_DELIVERED))
        == 1
    )
