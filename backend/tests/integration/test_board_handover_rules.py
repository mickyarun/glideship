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

"""Who may hand a card over, and the handovers that are refused."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.models.bud import BUDStatus
from tests.integration.board_api_support import ok, person, put_role
from tests.integration.board_handover_support import card, desk, hand_over, preview, stubbed
from tests.integration.board_notify_support import fake_slack
from tests.integration.bud_lifecycle_reads import load_bud, timeline
from tests.integration.bud_lifecycle_support import (
    app_database_blocked as app_database_blocked,
)
from tests.integration.leave_support import give_custom_role
from tests.integration.scan_features_bugs_support import Factory, new_bud

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _slack(monkeypatch: pytest.MonkeyPatch, pg_session_factory: Factory) -> None:
    fake_slack(monkeypatch, pg_session_factory)


@pytest.mark.parametrize(
    ("role", "missing"),
    [("developer", "buds:create"), ("sales", "workspace:engineering")],
)
async def test_an_editor_needs_the_engineering_permissions(
    client: AsyncClient, pg_session_factory: Factory, role: str, missing: str
) -> None:
    """403 HANDOVER_NEEDS_PERMISSION naming the missing permission, preview and confirm."""
    d = await desk(client, pg_session_factory)
    editor = await person(pg_session_factory, d.org, role)
    await put_role(client, d.pm, d.key, editor.id, "editor")
    url = await card(client, d, description_md="x")
    with stubbed():
        for res in (await preview(client, editor, url), await hand_over(client, editor, url)):
            assert res.status_code == 403
            assert res.json()["code"] == "HANDOVER_NEEDS_PERMISSION"
            assert res.json()["permission"] == missing
    listed = ok(await client.get(f"{url}/handovers", headers=editor.headers))
    assert listed == {"items": [], "can_hand_over": False}


async def test_a_viewer_cannot_hand_over(client: AsyncClient, pg_session_factory: Factory) -> None:
    """The board role comes first: a viewer with every permission is 403."""
    d = await desk(client, pg_session_factory)
    other_pm = await person(pg_session_factory, d.org, "pm")
    await put_role(client, d.pm, d.key, other_pm.id, "viewer")
    url = await card(client, d, description_md="x")
    with stubbed():
        assert (await hand_over(client, other_pm, url)).status_code == 403


async def test_linking_needs_buds_edit(client: AsyncClient, pg_session_factory: Factory) -> None:
    """Create rights alone don't let someone attach a card to an existing BUD."""
    d = await desk(client, pg_session_factory)
    maker = await person(pg_session_factory, d.org, "pm")
    await give_custom_role(
        pg_session_factory,
        d.org,
        maker.id,
        "boards:view",
        "workspace:engineering",
        "buds:view",
        "buds:create",
    )
    await put_role(client, d.pm, d.key, maker.id, "editor")
    bud_id = await new_bud(pg_session_factory, d.org, 1, status=BUDStatus.DESIGN)
    url = await card(client, d)
    with stubbed():
        res = await hand_over(client, maker, url, mode="link", bud_id=str(bud_id))
    assert res.status_code == 403 and res.json()["permission"] == "buds:edit"


async def test_board_and_card_state_refuse(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """Handover off is 409 HANDOVER_DISABLED; an archived card is 409."""
    off = await desk(client, pg_session_factory, handover=False)
    off_url = await card(client, off, description_md="x")
    on = await desk(client, pg_session_factory)
    archived = await card(client, on, description_md="x")
    ok(await client.post(f"{archived}/archive", headers=on.pm.headers))
    with stubbed():
        disabled = await hand_over(client, off.pm, off_url)
        gone = await hand_over(client, on.pm, archived)
    assert disabled.status_code == 409 and disabled.json()["code"] == "HANDOVER_DISABLED"
    assert gone.status_code == 409 and "archived" in gone.json()["detail"]


async def test_the_tech_plan_needs_requirements(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """422 HANDOVER_NEEDS_REQUIREMENTS on an empty card; bud and design are fine."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d)
    with stubbed():
        for res in (
            await preview(client, d.pm, url, target_status="tech_arch"),
            await hand_over(client, d.pm, url, target_status="tech_arch"),
        ):
            assert res.status_code == 422
            assert res.json()["code"] == "HANDOVER_NEEDS_REQUIREMENTS"
        shown = ok(await preview(client, d.pm, url, target_status="design"))
    assert "NO_REQUIREMENTS" in [w["code"] for w in shown["warnings"]]


async def test_link_mode_leaves_the_bud_alone_and_keeps_one_origin(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """Linked once; another card is 409 BUD_HAS_OTHER_ORIGIN; the same card BUD_ALREADY_LINKED."""
    d = await desk(client, pg_session_factory)
    bud_id = await new_bud(pg_session_factory, d.org, 7, status=BUDStatus.DESIGN)
    closed = await new_bud(pg_session_factory, d.org, 8, status=BUDStatus.CLOSED)
    first, second = await card(client, d), await card(client, d)
    link = {"mode": "link", "bud_id": str(bud_id)}
    with stubbed() as spawn:
        shown = ok(await preview(client, d.pm, first, **link))
        made = ok(await hand_over(client, d.pm, first, **link), 201)
        other = await hand_over(client, d.pm, second, **link)
        again = await hand_over(client, d.pm, first, **link)
        shut = await hand_over(client, d.pm, second, mode="link", bud_id=str(closed))
    assert (shown["mode"], shown["title"], shown["target_status"]) == ("link", "BUD 7", "design")
    assert made["handover"]["linked_existing"] is True
    assert made["handover"]["target_status"] is None
    assert (other.status_code, other.json()["code"]) == (409, "BUD_HAS_OTHER_ORIGIN")
    assert (again.status_code, again.json()["code"]) == (409, "BUD_ALREADY_LINKED")
    assert (shut.status_code, shut.json()["code"]) == (409, "BUD_NOT_OPEN")
    bud = await load_bud(pg_session_factory, bud_id)
    assert (bud.status, bud.title, bud.assignee_id) == (BUDStatus.DESIGN, "BUD 7", None)
    assert await timeline(pg_session_factory, bud_id, "status_change") == []
    [event] = await timeline(pg_session_factory, bud_id, "handed_over_from_board")
    assert event["linked"] is True
    assert spawn.await_count == 0


async def test_an_unknown_bud_is_404(client: AsyncClient, pg_session_factory: Factory) -> None:
    """Linking to a BUD in no org of the caller's is 404, not a leak."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d)
    with stubbed():
        res = await hand_over(client, d.pm, url, mode="link", bud_id=str(uuid.uuid4()))
    assert res.status_code == 404
