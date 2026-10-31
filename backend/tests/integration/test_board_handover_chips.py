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

"""BUD chips on cards, the BUD's Origin panel, and the agent options a handover passes on."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import event, func, select

from app.models.bud import BUDDocument
from app.repositories.board_card_filters import CardQuery
from app.repositories.board_card_summary import BoardCardSummaryRepository
from tests.integration.board_api_support import BOARDS, ok, page, person
from tests.integration.board_handover_return_support import (
    BUDS,
    SECRET_TITLE,
    bud_of,
    handed,
    send_back,
)
from tests.integration.board_handover_support import card, desk, hand_over, stubbed
from tests.integration.board_notify_support import fake_slack
from tests.integration.bud_lifecycle_reads import load_bud
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


async def test_chips_name_each_bud_without_its_title(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """Key and statuses for everyone on the board; only engineering may open the BUD."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="x")
    live = await handed(client, d.pm, url, overrides={"title": SECRET_TITLE})
    back = await handed(client, d.pm, url, overrides={"title": SECRET_TITLE})
    ok(await send_back(client, d.pm, bud_of(back)))
    viewer = await person(pg_session_factory, d.org, None)
    await give_custom_role(pg_session_factory, d.org, viewer.id, "boards:view")

    mine = ok(await client.get(url, headers=d.pm.headers))
    theirs = ok(await client.get(url, headers=viewer.headers))
    listed = await page(client, viewer, d.key, d.stage("Ready for dev"))

    assert [(c["bud_id"], c["status"], c["handover_status"]) for c in mine["handovers"]] == [
        (str(bud_of(live)), "bud", "active"),
        (str(bud_of(back)), "discarded", "returned"),
    ]
    assert mine["handovers"][0]["bud_key"] == live["handover"]["bud_key"]
    assert [c["can_open_bud"] for c in mine["handovers"]] == [True, True]
    assert [c["can_open_bud"] for c in theirs["handovers"]] == [False, False]
    assert mine["delivery"] == theirs["delivery"] == "in_progress"
    [summary] = listed["items"]
    # A page's chips carry no history; the card's own detail does.
    assert summary["handovers"] == [{**c, "history": []} for c in theirs["handovers"]]
    assert [len(c["history"]) for c in theirs["handovers"]] == [0, 1]
    assert SECRET_TITLE not in json.dumps(theirs) + json.dumps(listed)


async def test_chips_load_in_the_page_query(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """One statement for a page however many handovers its cards hold."""
    d = await desk(client, pg_session_factory)
    for i in range(4):
        url = await card(client, d, f"C{i}", description_md="x")
        for _ in range(i):
            await handed(client, d.pm, url)
    ready = uuid.UUID(d.stage("Ready for dev"))

    async with pg_session_factory() as db:
        repo = BoardCardSummaryRepository(db, org_id=d.org)
        with _statements(pg_session_factory) as seen:
            rows = await repo.list_summaries(
                uuid.UUID(d.board["board"]["id"]), CardQuery(stage_id=ready, limit=50)
            )
    assert len(seen) == 1
    assert sorted(len(r.handovers) for r in rows) == [1, 2, 3]
    with _statements(pg_session_factory) as small:
        await page(client, d.pm, d.key, str(ready), limit=1)
    with _statements(pg_session_factory) as large:
        await page(client, d.pm, d.key, str(ready), limit=3)
    assert len(small) == len(large)


async def test_the_origin_panel_shows_the_card_to_its_board(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """Card, board, newest comments first in pages, and the card's handovers."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, "Pricing page", description_md="x")
    made = await handed(client, d.pm, url)
    for text in ("one", "two", "three"):
        ok(await client.post(f"{url}/comments", json={"body": text}, headers=d.pm.headers), 201)
    origin_url = f"{BUDS}/{bud_of(made)}/origin"

    first = ok(await client.get(origin_url, params={"limit": 2}, headers=d.pm.headers))
    cursor = first["comments"]["next_cursor"]
    rest = ok(
        await client.get(origin_url, params={"limit": 2, "cursor": cursor}, headers=d.pm.headers)
    )

    assert first["hidden"] is False
    assert first["card"] == {
        "key": made["card"]["key"],
        "number": made["card"]["number"],
        "title": "Pricing page",
        "board": {"key": d.key, "name": d.board["board"]["name"]},
    }
    assert [c["body"] for c in first["comments"]["items"]] == ["three", "two"]
    assert [c["body"] for c in rest["comments"]["items"]] == ["one"]
    assert rest["comments"]["next_cursor"] is None
    assert [h["bud_id"] for h in first["handovers"]] == [str(bud_of(made))]


async def test_the_origin_panel_hides_a_board_the_caller_cant_open(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """No board access: hidden, with nothing about the board; no handover: no card."""
    d = await desk(client, pg_session_factory)
    made = await handed(client, d.pm, await card(client, d, description_md="x"))
    outsider = await person(pg_session_factory, d.org, None)
    await give_custom_role(
        pg_session_factory, d.org, outsider.id, "workspace:engineering", "buds:view"
    )
    plain = ok(await client.post(f"{BUDS}/", json={"title": "Plain"}, headers=d.pm.headers), 201)

    hidden = ok(await client.get(f"{BUDS}/{bud_of(made)}/origin", headers=outsider.headers))
    none = ok(await client.get(f"{BUDS}/{plain['id']}/origin", headers=d.pm.headers))
    missing = await client.get(f"{BUDS}/{uuid.uuid4()}/origin", headers=d.pm.headers)

    assert hidden == {"card": None, "hidden": True, "comments": None, "handovers": []}
    assert none == {"card": None, "hidden": False, "comments": None, "handovers": []}
    assert missing.status_code == 404


async def test_the_confirm_passes_the_agent_options_on(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """Phase switches reach the BUD; a stage skill pick that doesn't exist is a 422."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="x")
    phases = {"bud": False, "design": True, "closed": True}
    made = await handed(client, d.pm, url, auto_generate_phases=phases)
    assert (await load_bud(pg_session_factory, bud_of(made))).auto_generate_phases == phases

    async with pg_session_factory() as db:
        before = await db.scalar(select(func.count()).where(BUDDocument.org_id == d.org))
    with stubbed():
        refused = await hand_over(
            client, d.pm, url, stage_skill_overrides={"design": str(uuid.uuid4())}
        )
    async with pg_session_factory() as db:
        after = await db.scalar(select(func.count()).where(BUDDocument.org_id == d.org))
    assert refused.status_code == 422, refused.text
    assert before == after
    listed = ok(
        await client.get(
            f"{BOARDS}/{d.key}/cards/{made['card']['number']}/handovers", headers=d.pm.headers
        )
    )
    assert len(listed["items"]) == 1
