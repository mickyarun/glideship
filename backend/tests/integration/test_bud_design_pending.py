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

"""``design_pending`` on the BUD page: a card handed over straight to design, not designed yet."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.models.bud import BUDDesign, BUDDesignStatus, BUDStatus
from tests.integration.board_api_support import ok
from tests.integration.board_handover_return_support import BUDS, bud_of, handed, set_status
from tests.integration.board_handover_support import Desk, card, desk
from tests.integration.board_notify_support import fake_slack
from tests.integration.bud_lifecycle_support import (
    app_database_blocked as app_database_blocked,
)
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration

DESIGN_ON = {"design": True}


@pytest.fixture(autouse=True)
def _slack(monkeypatch: pytest.MonkeyPatch, pg_session_factory: Factory) -> None:
    fake_slack(monkeypatch, pg_session_factory)


async def _pending(client: AsyncClient, d: Desk, bud_id: uuid.UUID | str) -> bool:
    return bool(ok(await client.get(f"{BUDS}/{bud_id}", headers=d.pm.headers))["design_pending"])


async def test_pending_until_a_design_exists(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """Landed at design with generation on: pending; any design row clears it."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="x")
    made = await handed(client, d.pm, url, target_status="design", auto_generate_phases=DESIGN_ON)
    bud_id = bud_of(made)
    assert await _pending(client, d, bud_id) is True

    async with pg_session_factory() as db:
        db.add(BUDDesign(org_id=d.org, bud_id=bud_id, status=BUDDesignStatus.FAILED))
        await db.commit()
    assert await _pending(client, d, bud_id) is False


async def test_not_pending_without_generation_a_design_landing_or_a_handover(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """Design generation off, landed at bud, or a BUD moved to design by hand: never pending."""
    d = await desk(client, pg_session_factory)
    off = await handed(
        client, d.pm, await card(client, d, "Off", description_md="x"), target_status="design"
    )
    at_bud = await handed(
        client,
        d.pm,
        await card(client, d, "At bud", description_md="x"),
        target_status="bud",
        auto_generate_phases=DESIGN_ON,
    )
    plain = ok(
        await client.post(
            f"{BUDS}/",
            json={"title": "Plain", "auto_generate_phases": DESIGN_ON},
            headers=d.pm.headers,
        ),
        201,
    )
    await set_status(pg_session_factory, uuid.UUID(plain["id"]), BUDStatus.DESIGN)
    await set_status(pg_session_factory, bud_of(at_bud), BUDStatus.DESIGN)

    assert await _pending(client, d, bud_of(off)) is False
    assert await _pending(client, d, bud_of(at_bud)) is False
    assert await _pending(client, d, plain["id"]) is False
