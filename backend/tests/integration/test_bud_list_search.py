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

"""``GET /buds/?q=``: open BUDs by title or key, capped, for the handover link picker."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient

from app.config import settings
from app.models.bud import BUDStatus
from tests.integration.board_api_support import Person, ok, person
from tests.integration.board_handover_return_support import BUDS, set_status
from tests.integration.bud_lifecycle_support import (
    app_database_blocked as app_database_blocked,
)
from tests.integration.bud_lifecycle_support import stub_externals
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration


async def _bud(client: AsyncClient, who: Person, title: str) -> dict[str, Any]:
    with stub_externals():
        made = await client.post(f"{BUDS}/", json={"title": title}, headers=who.headers)
    return dict(ok(made, 201))


async def _titles(client: AsyncClient, who: Person, **params: str) -> list[str]:
    listed = ok(await client.get(f"{BUDS}/", params=params, headers=who.headers))
    return [item["title"] for item in listed]


async def test_search_finds_open_buds_by_title_or_key(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """Title words and BUD keys (with or without the prefix and padding); never closed ones."""
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    pricing = await _bud(client, pm, "Pricing page")
    await _bud(client, pm, "Checkout flow")
    shipped = await _bud(client, pm, "Pricing table v1")
    await set_status(pg_session_factory, uuid.UUID(shipped["id"]), BUDStatus.CLOSED)
    other = await person(pg_session_factory, await new_org(pg_session_factory), "pm")
    await _bud(client, other, "Pricing elsewhere")
    number = pricing["bud_number"]

    assert await _titles(client, pm, q="pricing") == ["Pricing page"]
    assert await _titles(client, pm, q=f"BUD-{number:03d}") == ["Pricing page"]
    assert await _titles(client, pm, q=f"bud-{number}") == ["Pricing page"]
    assert await _titles(client, pm, q=str(number)) == ["Pricing page"]
    assert await _titles(client, pm, q="100%") == []
    assert sorted(await _titles(client, pm)) == [
        "Checkout flow",
        "Pricing page",
        "Pricing table v1",
    ]


async def test_search_is_capped_by_the_setting(
    client: AsyncClient, pg_session_factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """At most BOARDS_HANDOVER_LINK_SEARCH_LIMIT results, newest first."""
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    for title in ("Flow one", "Flow two", "Flow three"):
        await _bud(client, pm, title)
    monkeypatch.setattr(settings.boards, "handover_link_search_limit", 2)

    assert await _titles(client, pm, q="flow") == ["Flow three", "Flow two"]
    assert len(await _titles(client, pm)) == 3
