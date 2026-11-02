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

"""The priority a handover gives its BUD: the dialog's, else the card's, else P2."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.integration.board_api_support import ok
from tests.integration.board_handover_return_support import BUDS, bud_of, handed, send_back
from tests.integration.board_handover_support import card, desk
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


async def test_a_new_bud_takes_the_dialogs_priority_else_the_cards_else_p2(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """Omitted: the card's priority, P2 for a card with none; sent: the one picked."""
    d = await desk(client, pg_session_factory)
    urgent = await card(client, d, "Urgent", description_md="x", priority="P1")
    plain = await card(client, d, "Plain", description_md="x")

    from_card = await handed(client, d.pm, urgent)
    fallback = await handed(client, d.pm, plain)
    picked = await handed(client, d.pm, urgent, priority="P0")

    assert (await load_bud(pg_session_factory, bud_of(from_card))).priority == "P1"
    assert (await load_bud(pg_session_factory, bud_of(fallback))).priority == "P2"
    assert (await load_bud(pg_session_factory, bud_of(picked))).priority == "P0"


async def test_handing_over_again_applies_the_picked_priority(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """The sent-back BUD comes back with the dialog's priority, same BUD."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="x", priority="P1")
    first = await handed(client, d.pm, url)
    ok(await send_back(client, d.pm, bud_of(first)))

    again = await handed(client, d.pm, url, priority="P3")

    assert bud_of(again) == bud_of(first)
    assert (await load_bud(pg_session_factory, bud_of(again))).priority == "P3"


async def test_a_link_ignores_the_priority(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """The linked BUD keeps its own priority."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="x", priority="P0")
    made = ok(
        await client.post(
            f"{BUDS}/", json={"title": "Existing", "priority": "P3"}, headers=d.pm.headers
        ),
        201,
    )

    linked = await handed(client, d.pm, url, mode="link", bud_id=made["id"], priority="P0")

    assert str(bud_of(linked)) == made["id"]
    assert (await load_bud(pg_session_factory, bud_of(linked))).priority == "P3"
