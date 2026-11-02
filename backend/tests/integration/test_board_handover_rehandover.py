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

"""Handing a card over again after a send-back, and a BUD discarded on the dev side."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.board_enums import BoardCardEventType
from app.models.bud import BUDStatus
from app.models.bud_version import BUDVersion
from tests.integration.board_api_support import ok, person, put_role
from tests.integration.board_handover_return_support import (
    BUDS,
    board_events,
    bud_of,
    card_events,
    handed,
    send_back,
)
from tests.integration.board_handover_support import card, card_stage, desk, stubbed
from tests.integration.board_notify_support import fake_slack
from tests.integration.bud_lifecycle_reads import load_bud, timeline
from tests.integration.bud_lifecycle_support import (
    app_database_blocked as app_database_blocked,
)
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _slack(monkeypatch: pytest.MonkeyPatch, pg_session_factory: Factory) -> None:
    fake_slack(monkeypatch, pg_session_factory)


async def test_handing_over_again_restores_the_same_bud(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """Same BUD and number, refreshed requirements in a version by the new hand, one row."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="First idea")
    first = await handed(client, d.pm, url)
    bud_id = bud_of(first)
    number = (await load_bud(pg_session_factory, bud_id)).bud_number
    ok(await send_back(client, d.pm, bud_id))
    second_pm = await person(pg_session_factory, d.org, "pm")
    await put_role(client, d.pm, d.key, second_pm.id, "editor")
    body = {"description_md": "Sharper idea"}
    ok(await client.patch(url, json=body, headers=d.pm.headers))

    again = await handed(client, second_pm, url, target_status="design")

    assert bud_of(again) == bud_id
    assert again["handover"]["id"] == first["handover"]["id"]
    assert (again["handover"]["status"], again["handover"]["return_reason"]) == ("active", None)
    bud = await load_bud(pg_session_factory, bud_id)
    assert (bud.bud_number, bud.status) == (number, BUDStatus.DESIGN)
    assert bud.requirements_md is not None and bud.requirements_md.startswith("Sharper idea")
    async with pg_session_factory() as db:
        newest = await db.scalar(
            select(BUDVersion)
            .where(BUDVersion.bud_id == bud_id)
            .order_by(BUDVersion.edited_at.desc())
            .limit(1)
        )
    assert newest is not None and newest.edited_by == second_pm.id
    assert newest.snapshot["requirements_md"].startswith("Sharper idea")
    restored = [
        e for e in await timeline(pg_session_factory, bud_id, "status_change") if e.get("restored")
    ]
    assert [(e["to"], e["via"]) for e in restored] == [("bud", "handover")]
    origins = await timeline(pg_session_factory, bud_id, "handed_over_from_board")
    assert [o.get("again", False) for o in origins] == [False, True]
    card_id = first["card"]["id"]
    assert str(await card_stage(pg_session_factory, card_id)) == d.stage("Ready for dev")
    events = await card_events(pg_session_factory, card_id, BoardCardEventType.HANDED_OVER)
    assert [e.get("again", False) for e in events] == [False, True]
    listed = ok(await client.get(f"{url}/handovers", headers=d.pm.headers))
    assert len(listed["items"]) == 1


async def test_a_retry_of_the_second_handover_replays_it(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """The reactivated row takes the new key, so a retried confirm returns it."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="x")
    first = await handed(client, d.pm, url)
    ok(await send_back(client, d.pm, bud_of(first)))
    key = "0b6f0d6e-7c55-4f0c-9b16-3a4f8c1d2e00"
    again = await handed(client, d.pm, url, key=key)
    replay = await handed(client, d.pm, url, key=key)
    assert replay["handover"] == again["handover"]


async def test_a_dev_side_discard_keeps_the_handover_live(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """Discarded from the BUD: the row stays active, the chip shows it, delivery ignores it."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="x")
    made = await handed(client, d.pm, url)
    async with board_events(d) as events:
        with stubbed():
            ok(
                await client.patch(
                    f"{BUDS}/{bud_of(made)}", json={"status": "discarded"}, headers=d.pm.headers
                )
            )

    assert [e["event"] for e in events] == ["card_handovers_changed"]
    assert events[0]["card_id"] == made["card"]["id"]

    [row] = ok(await client.get(f"{url}/handovers", headers=d.pm.headers))["items"]
    assert (row["status"], row["bud_status"]) == ("active", "discarded")
    detail = ok(await client.get(url, headers=d.pm.headers))
    [chip] = detail["handovers"]
    assert (chip["status"], chip["handover_status"]) == ("discarded", "active")
    # A BUD discarded on the dev side no longer counts toward the card's delivery.
    assert detail["delivery"] == "none"
    # A fresh create on this card doesn't reuse it: only returned BUDs come back.
    second = await handed(client, d.pm, url)
    assert bud_of(second) != bud_of(made)
