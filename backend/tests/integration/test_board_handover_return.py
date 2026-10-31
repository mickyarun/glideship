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

"""Sending a BUD back to its card: when it's allowed, the card's move, comment and notices."""

from __future__ import annotations

import json
import uuid

import pytest
from httpx import AsyncClient

from app.models.board_enums import BoardCardEventType
from app.models.bud import BUDStatus
from tests.integration.board_api_support import ok, person
from tests.integration.board_handover_return_support import (
    BUDS,
    SECRET_TITLE,
    board_events,
    bud_of,
    card_comments,
    card_events,
    handed,
    send_back,
    set_status,
)
from tests.integration.board_handover_support import card, card_stage, desk
from tests.integration.board_notify_support import Slack, fake_slack, link_slack, notes
from tests.integration.bud_lifecycle_reads import load_bud, timeline
from tests.integration.bud_lifecycle_support import (
    app_database_blocked as app_database_blocked,
)
from tests.integration.leave_support import give_custom_role
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def slack(monkeypatch: pytest.MonkeyPatch, pg_session_factory: Factory) -> Slack:
    return fake_slack(monkeypatch, pg_session_factory)


@pytest.mark.parametrize("target", ["bud", "design", "tech_arch"])
async def test_a_bud_goes_back_before_development(
    client: AsyncClient, pg_session_factory: Factory, target: str
) -> None:
    """Discarded, returned with the reason, a comment by the sender, the card back in Ideas."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="Plans table")
    made = await handed(client, d.pm, url, target_status=target)
    bud_id = bud_of(made)

    back = ok(await send_back(client, d.pm, bud_id, "Wrong problem"))

    assert (back["status"], back["return_reason"]) == ("returned", "Wrong problem")
    assert back["returned_at"] is not None and back["bud_status"] == "discarded"
    assert (await load_bud(pg_session_factory, bud_id)).status is BUDStatus.DISCARDED
    [event] = await timeline(pg_session_factory, bud_id, "returned_to_board")
    assert (event["card_id"], event["reason"]) == (made["card"]["id"], "Wrong problem")
    card_id = made["card"]["id"]
    assert str(await card_stage(pg_session_factory, card_id)) == d.stage("Ideas")
    [comment] = await card_comments(pg_session_factory, card_id)
    assert comment.author_id == d.pm.id and comment.body.endswith("Wrong problem")
    [returned] = await card_events(pg_session_factory, card_id, BoardCardEventType.RETURNED)
    assert returned == {
        "bud_id": str(bud_id),
        "bud_key": made["handover"]["bud_key"],
        "comment_id": str(comment.id),
    }


async def test_development_keeps_the_bud(client: AsyncClient, pg_session_factory: Factory) -> None:
    """409 BUD_PAST_RETURN once development starts; nothing changes."""
    d = await desk(client, pg_session_factory)
    made = await handed(client, d.pm, await card(client, d, description_md="x"))
    await set_status(pg_session_factory, bud_of(made), BUDStatus.DEVELOPMENT)

    refused = await send_back(client, d.pm, bud_of(made))

    assert refused.status_code == 409
    assert refused.json() | {"detail": None} == {
        "code": "BUD_PAST_RETURN",
        "status": "development",
        "detail": None,
    }
    url = f"/api/v1/boards/{d.key}/cards/{made['card']['number']}/handovers"
    [row] = ok(await client.get(url, headers=d.pm.headers))["items"]
    assert row["status"] == "active"


async def test_only_a_live_handover_goes_back(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """A BUD made on the BUD board, or one already sent back: 409 HANDOVER_NOT_ACTIVE."""
    d = await desk(client, pg_session_factory)
    made = await handed(client, d.pm, await card(client, d, description_md="x"))
    ok(await send_back(client, d.pm, bud_of(made)))
    again = await send_back(client, d.pm, bud_of(made))
    plain = ok(await client.post(f"{BUDS}/", json={"title": "Plain"}, headers=d.pm.headers), 201)
    never = await send_back(client, d.pm, uuid.UUID(plain["id"]))
    missing = await send_back(client, d.pm, uuid.uuid4())

    assert again.status_code == never.status_code == 409
    assert again.json()["code"] == never.json()["code"] == "HANDOVER_NOT_ACTIVE"
    assert missing.status_code == 404


async def test_sending_back_needs_buds_edit(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """403 without ``buds:edit``; the handover stays live."""
    d = await desk(client, pg_session_factory)
    made = await handed(client, d.pm, await card(client, d, description_md="x"))
    reader = await person(pg_session_factory, d.org, None)
    await give_custom_role(
        pg_session_factory, d.org, reader.id, "workspace:engineering", "buds:view"
    )

    refused = await send_back(client, reader, bud_of(made))

    assert refused.status_code == 403
    assert (await load_bud(pg_session_factory, bud_of(made))).status is not BUDStatus.DISCARDED


async def test_the_card_waits_for_its_last_live_handover(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """With another BUD still live the card stays; the last send-back moves it to Ideas."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="x")
    first = await handed(client, d.pm, url)
    second = await handed(client, d.pm, url)
    card_id = first["card"]["id"]

    async with board_events(d) as stays:
        ok(await send_back(client, d.pm, bud_of(first)))
    assert str(await card_stage(pg_session_factory, card_id)) == d.stage("Ready for dev")
    async with board_events(d) as moves:
        ok(await send_back(client, d.pm, bud_of(second)))
    assert str(await card_stage(pg_session_factory, card_id)) == d.stage("Ideas")

    assert "card_moved" not in [e["event"] for e in stays]
    names = [e["event"] for e in moves]
    assert names.index("card_moved") < names.index("card_handover_returned")
    [returned] = [e for e in moves if e["event"] == "card_handover_returned"]
    assert returned["card_id"] == card_id
    assert returned["handover"] == {
        "id": second["handover"]["id"],
        "bud_id": str(bud_of(second)),
        "bud_key": second["handover"]["bud_key"],
        "bud_status": "discarded",
        "status": "returned",
    }


async def test_the_card_assignees_hear_without_the_bud_title(
    client: AsyncClient, pg_session_factory: Factory, slack: Slack
) -> None:
    """In-app row and DM to the assignee (not the sender); no BUD title on the board side."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="x", assignee_ids=[str(d.designer.id)])
    made = await handed(client, d.pm, url, overrides={"title": SECRET_TITLE})
    ids = await link_slack(pg_session_factory, d.org, d.designer.id, d.pm.id)
    await slack.flush()
    slack.posts.clear()

    async with board_events(d) as events:
        ok(await send_back(client, d.pm, bud_of(made), "Needs research"))
    posts = await slack.flush()

    [note] = [
        n
        for n in await notes(pg_session_factory, d.designer.id)
        if n.type == "board_handover_returned"
    ]
    key = made["handover"]["bud_key"]
    assert key in note.message and "Needs research" in note.message
    [dm] = slack.to(ids[d.designer.id])
    assert key in dm and "Needs research" in dm
    assert slack.to(ids[d.pm.id]) == []
    sent = json.dumps(events) + json.dumps(posts) + note.message
    assert SECRET_TITLE not in sent
