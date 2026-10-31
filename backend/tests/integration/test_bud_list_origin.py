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

"""Origin chips on the Delivery board's BUD list, and who sees them."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import event

from tests.integration.board_api_support import BOARDS, Person, ok, person
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


async def _origins(client: AsyncClient, who: Person) -> dict[str, Any]:
    listed = ok(await client.get(f"{BUDS}/", headers=who.headers))
    return {item["id"]: item["origin"] for item in listed}


async def test_a_board_member_sees_each_buds_origin_card(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """A live origin names the card and board; a plain or sent-back BUD has none."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="x")
    live = await handed(client, d.pm, url)
    back = await handed(client, d.pm, await card(client, d, "Other", description_md="x"))
    ok(await send_back(client, d.pm, bud_of(back)))
    plain = ok(await client.post(f"{BUDS}/", json={"title": "Plain"}, headers=d.pm.headers), 201)

    origins = await _origins(client, d.pm)

    assert origins[str(bud_of(live))] == {
        "card_key": live["card"]["key"],
        "board_key": d.key,
        "can_open": True,
    }
    assert origins[str(bud_of(back))] is None
    assert origins[plain["id"]] is None


async def test_no_origin_for_a_caller_who_cant_open_the_board(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """Engineering without boards, or outside a members-only board: null, as if never handed."""
    d = await desk(client, pg_session_factory)
    made = await handed(client, d.pm, await card(client, d, description_md="x"))
    no_boards = await person(pg_session_factory, d.org, None)
    await give_custom_role(
        pg_session_factory, d.org, no_boards.id, "workspace:engineering", "buds:view"
    )
    outsider = await person(pg_session_factory, d.org, None)
    await give_custom_role(
        pg_session_factory,
        d.org,
        outsider.id,
        "workspace:engineering",
        "buds:view",
        "boards:view",
    )
    assert (await _origins(client, outsider))[str(bud_of(made))] is not None
    members = {"visibility": "members"}
    ok(await client.patch(f"{BOARDS}/{d.key}", json=members, headers=d.pm.headers))

    assert (await _origins(client, no_boards))[str(bud_of(made))] is None
    assert (await _origins(client, outsider))[str(bud_of(made))] is None
    assert (await _origins(client, d.pm))[str(bud_of(made))] is not None


async def test_origins_load_in_one_query_for_the_page(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """The same number of statements for one handed-over BUD as for several."""
    d = await desk(client, pg_session_factory)
    await handed(client, d.pm, await card(client, d, "C0", description_md="x"))
    with _statements(pg_session_factory) as one:
        await _origins(client, d.pm)
    for i in range(1, 4):
        await handed(client, d.pm, await card(client, d, f"C{i}", description_md="x"))
    with _statements(pg_session_factory) as many:
        listed = await _origins(client, d.pm)

    assert sum(origin is not None for origin in listed.values()) == 4
    assert len(one) == len(many)
    assert sum("board_card_handovers" in sql for sql in many) == 1
