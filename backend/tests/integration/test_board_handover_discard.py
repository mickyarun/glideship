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

"""Discarded and deleted BUDs on a card, and the send-back's edges."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.models.board import Board
from app.models.board_enums import BoardCardEventType
from app.models.bud import BUDStatus
from tests.integration.board_api_support import BOARDS, ok
from tests.integration.board_handover_return_support import (
    BUDS,
    board_events,
    bud_of,
    card_events,
    handed,
    send_back,
    set_status,
)
from tests.integration.board_handover_support import Desk, card, card_stage, desk, stubbed
from tests.integration.board_notify_support import Slack, fake_slack, notes
from tests.integration.bud_lifecycle_support import (
    app_database_blocked as app_database_blocked,
)
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def slack(monkeypatch: pytest.MonkeyPatch, pg_session_factory: Factory) -> Slack:
    return fake_slack(monkeypatch, pg_session_factory)


async def _patch(client: AsyncClient, d: Desk, bud_id: uuid.UUID, status: str) -> None:
    with stubbed():
        ok(await client.patch(f"{BUDS}/{bud_id}", json={"status": status}, headers=d.pm.headers))


async def test_discarding_the_last_open_bud_delivers_the_card(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """One BUD in prod, one discarded on the dev side: fully delivered, once."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="x")
    shipped, dropped = await handed(client, d.pm, url), await handed(client, d.pm, url)
    card_id = shipped["card"]["id"]
    await set_status(pg_session_factory, bud_of(shipped), BUDStatus.UAT)
    await _patch(client, d, bud_of(shipped), "prod")
    assert await card_events(pg_session_factory, card_id, BoardCardEventType.FULLY_DELIVERED) == []

    await _patch(client, d, bud_of(dropped), "discarded")

    [fully] = await card_events(pg_session_factory, card_id, BoardCardEventType.FULLY_DELIVERED)
    assert (fully["bud_id"], fully["bud_status"]) == (str(bud_of(dropped)), "discarded")
    assert ok(await client.get(url, headers=d.pm.headers))["delivery"] == "delivered"


async def test_a_deleted_bud_leaves_no_chip_and_no_delivery(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """Hard-deleted: the row stays with null BUD fields; no chip; delivery none."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="x")
    made = await handed(client, d.pm, url)
    ok(await client.delete(f"{BUDS}/{bud_of(made)}", headers=d.pm.headers), 204)

    [row] = ok(await client.get(f"{url}/handovers", headers=d.pm.headers))["items"]
    assert (row["bud_id"], row["bud_key"], row["bud_status"]) == (None, None, None)
    detail = ok(await client.get(url, headers=d.pm.headers))
    assert (detail["handovers"], detail["delivery"]) == ([], "none")


async def test_a_dev_discarded_bud_is_not_sent_back(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """409 HANDOVER_NOT_ACTIVE saying to restore it, not BUD_PAST_RETURN."""
    d = await desk(client, pg_session_factory)
    made = await handed(client, d.pm, await card(client, d, description_md="x"))
    await _patch(client, d, bud_of(made), "discarded")
    refused = await send_back(client, d.pm, bud_of(made))
    assert (refused.status_code, refused.json()["code"]) == (409, "HANDOVER_NOT_ACTIVE")
    assert (
        refused.json()["detail"]
        == f"{made['handover']['bud_key']} was discarded; restore it first."
    )


async def test_the_reason_is_posted_as_a_comment(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """A ``commented`` event and ``card_activity``; assignees hear only that it came back."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="x", assignee_ids=[str(d.designer.id)])
    made = await handed(client, d.pm, url)
    async with board_events(d) as events:
        ok(await send_back(client, d.pm, bud_of(made)))
    card_id = made["card"]["id"]
    [commented] = await card_events(pg_session_factory, card_id, BoardCardEventType.COMMENTED)
    [returned] = await card_events(pg_session_factory, card_id, BoardCardEventType.RETURNED)
    assert commented["comment_id"] == returned["comment_id"]
    assert {"event": "card_activity", "card_id": card_id}.items() <= next(
        e for e in events if e["event"] == "card_activity"
    ).items()
    kinds = [n.type for n in await notes(pg_session_factory, d.designer.id)]
    assert "board_card_comment" not in kinds and "board_handover_returned" in kinds


@pytest.mark.parametrize("why", ["no_return_stage", "archived_card", "archived_board"])
async def test_a_send_back_that_cannot_move_the_card_leaves_it(
    client: AsyncClient, pg_session_factory: Factory, why: str
) -> None:
    """The BUD goes back; the card stays in its stage."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="x")
    made = await handed(client, d.pm, url)
    card_id = made["card"]["id"]
    if why == "no_return_stage":
        async with pg_session_factory() as db:
            board_id = uuid.UUID(d.board["board"]["id"])
            await db.execute(
                update(Board).where(Board.id == board_id).values(return_stage_id=None)
            )
            await db.commit()
    elif why == "archived_card":
        ok(await client.post(f"{url}/archive", headers=d.pm.headers))
    else:
        ok(await client.post(f"{BOARDS}/{d.key}/archive", headers=d.pm.headers))

    back = ok(await send_back(client, d.pm, bud_of(made)))

    assert back["status"] == "returned"
    assert str(await card_stage(pg_session_factory, card_id)) == d.stage("Ready for dev")


async def test_another_orgs_bud_is_404_on_the_bud_routes(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """Send-back and Origin don't find a BUD of another org."""
    d = await desk(client, pg_session_factory)
    made = await handed(client, d.pm, await card(client, d, description_md="x"))
    other = await desk(client, pg_session_factory)
    returned = await send_back(client, other.pm, bud_of(made))
    origin = await client.get(f"{BUDS}/{bud_of(made)}/origin", headers=other.pm.headers)
    assert returned.status_code == origin.status_code == 404
