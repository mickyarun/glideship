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

"""Each handover's send-backs and re-handovers, from the card's events, newest first."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import event, select

from app.config import settings
from app.models.user import User
from tests.integration.board_api_support import ok, person
from tests.integration.board_handover_return_support import BUDS, bud_of, handed, send_back
from tests.integration.board_handover_support import card, desk
from tests.integration.board_notify_support import fake_slack
from tests.integration.bud_lifecycle_support import (
    app_database_blocked as app_database_blocked,
)
from tests.integration.leave_support import give_custom_role
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _slack(monkeypatch: pytest.MonkeyPatch, pg_session_factory: Factory) -> None:
    fake_slack(monkeypatch, pg_session_factory)


@contextmanager
def _statements(factory: Factory) -> Iterator[list[str]]:
    engine = factory.kw["bind"].sync_engine
    seen: list[str] = []

    def _record(*args: Any) -> None:
        seen.append(args[2])

    event.listen(engine, "before_cursor_execute", _record)
    try:
        yield seen
    finally:
        event.remove(engine, "before_cursor_execute", _record)


async def _name(factory: Factory, user_id: uuid.UUID) -> str:
    async with factory() as db:
        return str(await db.scalar(select(User.name).where(User.id == user_id)))


def _kinds(history: list[dict[str, Any]]) -> list[tuple[str, str | None]]:
    return [(h["kind"], h["reason"]) for h in history]


async def test_history_lists_send_backs_and_re_handovers_newest_first(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """The handovers list, card detail and confirm agree; board viewers see it too."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="x")
    first = await handed(client, d.pm, url)
    ok(await send_back(client, d.pm, bud_of(first), "Scope is wrong"))
    await handed(client, d.pm, url)
    ok(await send_back(client, d.pm, bud_of(first), "Still unclear"))
    again = await handed(client, d.pm, url)
    viewer = await person(pg_session_factory, d.org, None)
    await give_custom_role(pg_session_factory, d.org, viewer.id, "boards:view")

    [item] = ok(await client.get(f"{url}/handovers", headers=viewer.headers))["items"]
    [chip] = ok(await client.get(url, headers=d.pm.headers))["handovers"]

    expected = [
        ("handed_over_again", None),
        ("returned", "Still unclear"),
        ("handed_over_again", None),
        ("returned", "Scope is wrong"),
    ]
    assert _kinds(item["history"]) == expected
    assert chip["history"] == item["history"] == again["handover"]["history"]
    assert {h["by_name"] for h in item["history"]} == {await _name(pg_session_factory, d.pm.id)}
    stamps = [h["at"] for h in item["history"]]
    assert stamps == sorted(stamps, reverse=True)
    assert item["bud_title"] is None
    origin = ok(await client.get(f"{BUDS}/{bud_of(first)}/origin", headers=d.pm.headers))
    assert origin["handovers"][0]["history"] == item["history"]


async def test_history_is_capped_and_one_query(
    client: AsyncClient, pg_session_factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """At most BOARDS_HANDOVER_HISTORY_LIMIT per handover; longer history, no more queries."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="x")
    first = await handed(client, d.pm, url)
    plain = await handed(client, d.pm, url)
    ok(await send_back(client, d.pm, bud_of(first)))
    await handed(client, d.pm, url)
    with _statements(pg_session_factory) as short:
        ok(await client.get(f"{url}/handovers", headers=d.pm.headers))
    for _ in range(2):
        ok(await send_back(client, d.pm, bud_of(first)))
        await handed(client, d.pm, url)
    with _statements(pg_session_factory) as long:
        listed = ok(await client.get(f"{url}/handovers", headers=d.pm.headers))
    monkeypatch.setattr(settings.boards, "handover_history_limit", 2)
    capped = ok(await client.get(f"{url}/handovers", headers=d.pm.headers))

    by_bud = {i["bud_id"]: i["history"] for i in listed["items"]}
    assert len(by_bud[str(bud_of(first))]) == 6
    assert by_bud[str(bud_of(plain))] == []
    assert len(short) == len(long)
    assert sum("board_card_events" in sql for sql in long) == 1
    capped_by_bud = {i["bud_id"]: i["history"] for i in capped["items"]}
    assert capped_by_bud[str(bud_of(first))] == by_bud[str(bud_of(first))][:2]
