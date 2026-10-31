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

"""A handover's live events, two confirms racing on one key, and a failed stage start."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest
from httpx import AsyncClient

from app.models.bud import BUDStatus
from app.services import event_bus
from tests.integration.board_api_support import ok
from tests.integration.board_handover_support import card, desk, hand_over, stubbed
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


async def test_the_board_hears_the_move_and_the_handover(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """``card_moved`` into the handover stage, then ``card_handed_over`` with the handover."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="x")
    queue = event_bus.subscribe(f"board:{d.board['board']['id']}")
    try:
        with stubbed():
            made = ok(await hand_over(client, d.pm, url), 201)
        await asyncio.sleep(0)
        events: list[dict[str, Any]] = []
        while not queue.empty():
            events.append(queue.get_nowait()["data"])
    finally:
        event_bus.unsubscribe(f"board:{d.board['board']['id']}", queue)

    names = [e["event"] for e in events]
    assert names == ["card_moved", "card_handed_over"]
    moved, handed = events
    assert moved["card"]["stage_id"] == d.stage("Ready for dev")
    assert handed["card_id"] == made["card"]["id"]
    assert handed["handover"] == made["handover"]
    assert handed["actor_id"] == str(d.pm.id)


async def test_a_double_click_makes_one_bud(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """Two confirms at once with one key: the second waits on the card and replays the first."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="x")
    key = uuid.uuid4()
    with stubbed():
        results = await asyncio.gather(
            hand_over(client, d.pm, url, key=key), hand_over(client, d.pm, url, key=key)
        )
    first, second = (ok(res, 201) for res in results)
    assert first["handover"] == second["handover"]
    listed = ok(await client.get(f"{url}/handovers", headers=d.pm.headers))
    assert len(listed["items"]) == 1


async def test_a_failed_stage_start_keeps_the_handover(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """The agent call failing after commit is logged; the BUD and handover stay saved."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="x")
    with stubbed() as spawn:
        spawn.side_effect = RuntimeError("queue full")
        made = ok(
            await hand_over(
                client, d.pm, url, target_status="design", auto_generate_phases={"design": True}
            ),
            201,
        )
    assert spawn.await_count == 1
    bud = await load_bud(pg_session_factory, uuid.UUID(made["handover"]["bud_id"]))
    assert bud.status is BUDStatus.DESIGN
    listed = ok(await client.get(f"{url}/handovers", headers=d.pm.headers))
    assert [h["bud_id"] for h in listed["items"]] == [made["handover"]["bud_id"]]
