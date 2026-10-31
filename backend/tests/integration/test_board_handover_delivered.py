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

"""A handed-over BUD reaching prod: the card's delivered events, notices and roll-up."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.models.board_enums import BoardCardEventType
from app.models.bud import BUDDocument, BUDStatus
from app.services.bud_closure import on_bud_closed
from tests.integration.board_api_support import ok
from tests.integration.board_handover_return_support import (
    BUDS,
    board_events,
    bud_of,
    card_events,
    handed,
    set_status,
)
from tests.integration.board_handover_support import Desk, card, desk, stubbed
from tests.integration.board_notify_support import Slack, fake_slack, link_slack, notes
from tests.integration.bud_lifecycle_support import (
    app_database_blocked as app_database_blocked,
)
from tests.integration.bud_lifecycle_support import stub_externals
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration

DELIVERED = BoardCardEventType.DELIVERED
FULLY = BoardCardEventType.FULLY_DELIVERED


@pytest.fixture(autouse=True)
def slack(monkeypatch: pytest.MonkeyPatch, pg_session_factory: Factory) -> Slack:
    return fake_slack(monkeypatch, pg_session_factory)


async def _patch(client: AsyncClient, d: Desk, bud_id: uuid.UUID, status: str) -> None:
    with stubbed():
        ok(await client.patch(f"{BUDS}/{bud_id}", json={"status": status}, headers=d.pm.headers))


async def _auto_close(factory: Factory, org: uuid.UUID, bud_id: uuid.UUID) -> None:
    """What the release auto-close does: close, then the hook with no actor, then commit."""
    async with factory() as db:
        bud = await db.get(BUDDocument, bud_id)
        assert bud is not None
        bud.status = BUDStatus.CLOSED
        await db.flush()
        await db.refresh(bud)
        with stub_externals():
            await on_bud_closed(db, org, bud)
        await db.commit()


async def _delivered_notes(factory: Factory, user: uuid.UUID) -> list[str]:
    return [n.message for n in await notes(factory, user) if n.type == "board_handover_delivered"]


async def test_prod_then_close_delivers_once(
    client: AsyncClient, pg_session_factory: Factory, slack: Slack
) -> None:
    """The PATCH to prod writes delivered, fully delivered and one notice; closing adds none."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="x", assignee_ids=[str(d.designer.id)])
    made = await handed(client, d.pm, url)
    card_id, bud_id = made["card"]["id"], bud_of(made)
    ids = await link_slack(pg_session_factory, d.org, d.designer.id)
    await slack.flush()
    slack.posts.clear()
    await set_status(pg_session_factory, bud_id, BUDStatus.UAT)

    async with board_events(d) as events:
        await _patch(client, d, bud_id, "prod")
    await _patch(client, d, bud_id, "closed")
    await _auto_close(pg_session_factory, d.org, bud_id)
    await slack.flush()

    [delivered] = await card_events(pg_session_factory, card_id, DELIVERED)
    key = made["handover"]["bud_key"]
    assert delivered == {"bud_id": str(bud_id), "bud_key": key, "bud_status": "prod"}
    assert len(await card_events(pg_session_factory, card_id, FULLY)) == 1
    [note] = await _delivered_notes(pg_session_factory, d.designer.id)
    assert key in note
    [dm] = slack.to(ids[d.designer.id])
    assert key in dm and "reached prod" in dm
    changed = [e for e in events if e["event"] == "card_handovers_changed"]
    # At least once: the status change and the hook may commit separately.
    assert changed and {e["card_id"] for e in changed} == {card_id}
    detail = ok(await client.get(url, headers=d.pm.headers))
    assert detail["delivery"] == "delivered"


async def test_auto_close_delivers_once(client: AsyncClient, pg_session_factory: Factory) -> None:
    """Straight to closed by the release auto-close, twice: one delivered event."""
    d = await desk(client, pg_session_factory)
    made = await handed(client, d.pm, await card(client, d, description_md="x"))
    await _auto_close(pg_session_factory, d.org, bud_of(made))
    await _auto_close(pg_session_factory, d.org, bud_of(made))

    [delivered] = await card_events(pg_session_factory, made["card"]["id"], DELIVERED)
    assert delivered["bud_status"] == "closed"


async def test_fully_delivered_waits_for_every_live_bud(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """Two BUDs: the first in prod leaves the card in progress; the second delivers it."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="x")
    first, second = await handed(client, d.pm, url), await handed(client, d.pm, url)
    card_id = first["card"]["id"]
    for made in (first, second):
        await set_status(pg_session_factory, bud_of(made), BUDStatus.UAT)

    await _patch(client, d, bud_of(first), "prod")
    halfway = ok(await client.get(url, headers=d.pm.headers))
    assert await card_events(pg_session_factory, card_id, FULLY) == []
    await _patch(client, d, bud_of(second), "prod")
    done = ok(await client.get(url, headers=d.pm.headers))

    assert halfway["delivery"] == "in_progress"
    assert [c["status"] for c in halfway["handovers"]] == ["prod", "uat"]
    assert len(await card_events(pg_session_factory, card_id, DELIVERED)) == 2
    [fully] = await card_events(pg_session_factory, card_id, FULLY)
    assert fully["bud_id"] == str(bud_of(second))
    assert done["delivery"] == "delivered"


async def test_a_bud_without_a_card_closes_as_before(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """No origin card: the hook does nothing and the close succeeds."""
    d = await desk(client, pg_session_factory)
    plain = ok(await client.post(f"{BUDS}/", json={"title": "Plain"}, headers=d.pm.headers), 201)
    await set_status(pg_session_factory, uuid.UUID(plain["id"]), BUDStatus.UAT)
    await _patch(client, d, uuid.UUID(plain["id"]), "prod")
