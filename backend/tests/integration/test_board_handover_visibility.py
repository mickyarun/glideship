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

"""Who reads a handed-over BUD's title from a board, and who may preview a handover."""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient

from tests.integration.board_api_support import ok, person, put_role
from tests.integration.board_handover_return_support import SECRET_TITLE, board_events
from tests.integration.board_handover_support import card, desk, hand_over, preview, stubbed
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


async def test_a_board_only_viewer_never_reads_the_bud_title(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """Handovers list, card detail, card events and the live payload: keys, never the title."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="x")
    viewer = await person(pg_session_factory, d.org, None)
    await give_custom_role(pg_session_factory, d.org, viewer.id, "boards:view")
    async with board_events(d) as events:
        with stubbed():
            made = ok(await hand_over(client, d.pm, url, overrides={"title": SECRET_TITLE}), 201)

    listed = ok(await client.get(f"{url}/handovers", headers=viewer.headers))
    [item] = listed["items"]
    assert (item["bud_key"], item["bud_title"], item["can_open_bud"]) == (
        made["handover"]["bud_key"],
        None,
        False,
    )
    detail = ok(await client.get(url, headers=viewer.headers))
    history = ok(await client.get(f"{url}/events", headers=viewer.headers))
    seen = json.dumps([listed, detail, history, events])
    assert SECRET_TITLE not in seen
    assert made["handover"]["bud_key"] in seen

    mine = ok(await client.get(f"{url}/handovers", headers=d.pm.headers))
    assert (mine["items"][0]["bud_title"], mine["items"][0]["can_open_bud"]) == (
        SECRET_TITLE,
        True,
    )
    assert made["handover"]["bud_title"] == SECRET_TITLE


async def test_previewing_needs_buds_view(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """Similar BUDs are listed by title: buds:create alone is 403 naming buds:view."""
    d = await desk(client, pg_session_factory)
    maker = await person(pg_session_factory, d.org, None)
    await give_custom_role(
        pg_session_factory, d.org, maker.id, "boards:view", "workspace:engineering", "buds:create"
    )
    await put_role(client, d.pm, d.key, maker.id, "editor")
    url = await card(client, d, description_md="x")
    with stubbed():
        res = await preview(client, maker, url)
    assert res.status_code == 403
    assert res.json() == {
        "detail": res.json()["detail"],
        "code": "HANDOVER_NEEDS_PERMISSION",
        "permission": "buds:view",
    }
