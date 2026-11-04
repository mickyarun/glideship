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

"""The "Mark done" button in a follow-ups DM ticks the card's due date, for editors only."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from app.services.followups import mark_done
from app.services.followups.compose import MARK_DONE_ACTION
from tests.integration.board_api_support import BOARDS, card_team, ok, org_of
from tests.integration.followups_support import due_card
from tests.integration.leave_slack_support import click, connect_slack, signed
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration

DUE = "2030-03-11T08:00:00Z"

URL = "/api/v1/slack/interactions"


@pytest.fixture
def slack(monkeypatch: pytest.MonkeyPatch) -> dict[str, AsyncMock]:
    calls = {"ephemeral": AsyncMock(return_value=""), "update": AsyncMock(return_value="")}
    monkeypatch.setattr(mark_done, "post_ephemeral", calls["ephemeral"])
    monkeypatch.setattr(mark_done, "update_message", calls["update"])
    return calls


def _button(key: str) -> dict[str, Any]:
    return {
        "type": "section",
        "text": {"type": "mrkdwn", "text": f"*{key}*"},
        "accessory": {"type": "button", "action_id": MARK_DONE_ACTION, "value": key},
    }


def _press(team: str, slack_user: str, key: str, other: str) -> dict[str, Any]:
    payload = click(team, slack_user, MARK_DONE_ACTION, key)
    message = {"text": "Follow-ups", "blocks": [_button(key), _button(other)]}
    return {**payload, "message": message, "container": {"message_ts": "1700.1"}}


async def test_an_editor_marks_a_card_done_and_the_button_becomes_done(
    client: AsyncClient, pg_session_factory: Factory, slack: dict[str, AsyncMock]
) -> None:
    team = await card_team(client, pg_session_factory)
    org = await org_of(pg_session_factory, team.admin)
    workspace = await connect_slack(pg_session_factory, org, {team.editor.id: "UED"})
    card = await due_card(
        client, team.admin, team.key, "Ship it", "2030-03-11T08:00:00Z", team.editor
    )
    key = f"{team.key}-{card['number']}"

    body, headers = signed(_press(workspace, "UED", key, "OTHER-1"))
    assert (await client.post(URL, content=body, headers=headers)).status_code == 200

    url = f"{BOARDS}/{team.key}/cards/{card['number']}"
    assert ok(await client.get(url, headers=team.editor.headers))["due_done"] is True
    slack["ephemeral"].assert_not_awaited()
    (_token, channel, ts, _text, blocks), _ = slack["update"].await_args
    assert (channel, ts) == ("D1", "1700.1")
    assert "accessory" not in blocks[0] and blocks[0]["text"]["text"].endswith("Done")
    assert blocks[1]["accessory"]["value"] == "OTHER-1"


async def test_a_viewer_or_a_stranger_changes_nothing(
    client: AsyncClient, pg_session_factory: Factory, slack: dict[str, AsyncMock]
) -> None:
    team = await card_team(client, pg_session_factory)
    org = await org_of(pg_session_factory, team.admin)
    workspace = await connect_slack(pg_session_factory, org, {team.viewer.id: "UVW"})
    card = await due_card(
        client, team.admin, team.key, "Keep", "2030-03-11T08:00:00Z", team.viewer
    )
    key = f"{team.key}-{card['number']}"

    for who in ("UVW", "UNKNOWN"):
        body, headers = signed(_press(workspace, who, key, "OTHER-1"))
        assert (await client.post(URL, content=body, headers=headers)).status_code == 200

    url = f"{BOARDS}/{team.key}/cards/{card['number']}"
    assert ok(await client.get(url, headers=team.admin.headers))["due_done"] is False
    assert slack["ephemeral"].await_count == 2
    slack["update"].assert_not_awaited()
