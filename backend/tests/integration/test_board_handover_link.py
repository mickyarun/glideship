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

"""Linking a card to an existing BUD: what's refused, and two cards racing for one BUD."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from httpx import AsyncClient

from app.models.bud import BUDStatus
from tests.integration.board_api_support import ok
from tests.integration.board_handover_return_support import send_back
from tests.integration.board_handover_support import card, desk, hand_over, stubbed
from tests.integration.board_notify_support import fake_slack
from tests.integration.bud_lifecycle_support import (
    app_database_blocked as app_database_blocked,
)
from tests.integration.scan_features_bugs_support import Factory, new_bud, new_org

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _slack(monkeypatch: pytest.MonkeyPatch, pg_session_factory: Factory) -> None:
    fake_slack(monkeypatch, pg_session_factory)


async def test_another_orgs_bud_is_404(client: AsyncClient, pg_session_factory: Factory) -> None:
    """A BUD id from another org is not found, preview and confirm alike."""
    d = await desk(client, pg_session_factory)
    elsewhere = await new_bud(pg_session_factory, await new_org(pg_session_factory), 3)
    url = await card(client, d)
    with stubbed():
        for res in (
            await client.post(
                f"{url}/handovers/preview",
                json={"mode": "link", "bud_id": str(elsewhere)},
                headers=d.pm.headers,
            ),
            await hand_over(client, d.pm, url, mode="link", bud_id=str(elsewhere)),
        ):
            assert res.status_code == 404


@pytest.mark.parametrize("status", [BUDStatus.CLOSED, BUDStatus.DISCARDED])
async def test_a_closed_or_discarded_bud_is_not_open(
    client: AsyncClient, pg_session_factory: Factory, status: BUDStatus
) -> None:
    """409 BUD_NOT_OPEN, and no handover written."""
    d = await desk(client, pg_session_factory)
    bud_id = await new_bud(pg_session_factory, d.org, 4, status=status)
    url = await card(client, d)
    with stubbed():
        res = await hand_over(client, d.pm, url, mode="link", bud_id=str(bud_id))
    assert (res.status_code, res.json()["code"]) == (409, "BUD_NOT_OPEN")
    assert ok(await client.get(f"{url}/handovers", headers=d.pm.headers))["items"] == []


async def test_two_cards_linking_one_bud_at_once(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """The BUD's lock comes first: one link wins, the other is 409 BUD_HAS_OTHER_ORIGIN."""
    d = await desk(client, pg_session_factory)
    bud_id = await new_bud(pg_session_factory, d.org, 5, status=BUDStatus.DESIGN)
    first, second = await card(client, d), await card(client, d)
    link = {"mode": "link", "bud_id": str(bud_id)}
    with stubbed():
        results = await asyncio.gather(
            hand_over(client, d.pm, first, **link), hand_over(client, d.pm, second, **link)
        )
    codes = sorted(res.status_code for res in results)
    assert codes == [201, 409]
    [lost] = [res for res in results if res.status_code == 409]
    assert lost.json()["code"] == "BUD_HAS_OTHER_ORIGIN"


async def test_a_link_and_a_send_back_racing_on_one_bud(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """BUD, then card, on both paths: no deadlock; the link is refused, the send-back lands."""
    d = await desk(client, pg_session_factory)
    origin = await card(client, d, description_md="x")
    with stubbed():
        made = ok(await hand_over(client, d.pm, origin), 201)
    bud_id = uuid.UUID(made["handover"]["bud_id"])
    other = await card(client, d)
    with stubbed():
        linked, returned = await asyncio.wait_for(
            asyncio.gather(
                hand_over(client, d.pm, other, mode="link", bud_id=str(bud_id)),
                send_back(client, d.pm, bud_id),
            ),
            timeout=30,
        )
    # Other origin while it's live, not open once it's discarded: 409 either way.
    assert linked.json()["code"] in {"BUD_HAS_OTHER_ORIGIN", "BUD_NOT_OPEN"}
    assert linked.status_code == 409 and returned.status_code == 200
