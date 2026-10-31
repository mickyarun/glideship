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


"""Who stops hearing about a card, and a Slack failure never fails the change."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient

from app.models.notification import NotificationType
from app.models.user import User
from app.services.notifications import notice
from tests.integration.board_api_support import BOARDS, CardTeam, card_team, make_card, ok, org_of
from tests.integration.board_notify_support import Slack, fake_slack, link_slack, notes
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration


@pytest.fixture
def slack(monkeypatch: pytest.MonkeyPatch, pg_session_factory: Factory) -> Slack:
    return fake_slack(monkeypatch, pg_session_factory)


async def deactivate(factory: Factory, user_id: uuid.UUID) -> None:
    """Switch a person's login off."""
    async with factory() as db:
        user = await db.get(User, user_id)
        assert user is not None
        user.is_active = False
        await db.commit()


async def _assigned_card(
    client: AsyncClient, team: CardTeam, slack: Slack
) -> tuple[dict[str, Any], str]:
    """A card the editor and viewer are on, with the setup DMs cleared; its comments url."""
    card = await make_card(
        client,
        team.admin,
        team.key,
        assignee_ids=[str(team.editor.id), str(team.viewer.id)],
    )
    await slack.flush()
    slack.posts.clear()
    return card, f"{BOARDS}/{team.key}/cards/{card['number']}/comments"


async def _comment_notes(factory: Factory, user_id: uuid.UUID) -> int:
    rows = await notes(factory, user_id)
    return sum(n.type is NotificationType.BOARD_CARD_COMMENT for n in rows)


async def test_deactivated_or_removed_assignees_hear_nothing_about_comments(
    client: AsyncClient, pg_session_factory: Factory, slack: Slack
) -> None:
    team = await card_team(client, pg_session_factory)
    org = await org_of(pg_session_factory, team.admin)
    ids = await link_slack(pg_session_factory, org, team.editor.id, team.viewer.id)
    _card, comments = await _assigned_card(client, team, slack)
    await deactivate(pg_session_factory, team.editor.id)
    remove = f"{BOARDS}/{team.key}/members/{team.viewer.id}"
    ok(await client.delete(remove, headers=team.admin.headers))

    ok(await client.post(comments, json={"body": "Ping"}, headers=team.admin.headers), 201)
    assert await slack.flush() == []
    assert slack.to(ids[team.editor.id]) == [] and slack.to(ids[team.viewer.id]) == []
    assert await _comment_notes(pg_session_factory, team.editor.id) == 0
    assert await _comment_notes(pg_session_factory, team.viewer.id) == 0


async def test_a_slack_failure_never_fails_the_edit(
    client: AsyncClient,
    pg_session_factory: Factory,
    slack: Slack,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    team = await card_team(client, pg_session_factory)
    org = await org_of(pg_session_factory, team.admin)
    await link_slack(pg_session_factory, org, team.editor.id)

    def _broken(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("slack is down")

    monkeypatch.setattr(notice, "send_dm", _broken)
    body = {"assignee_ids": [str(team.editor.id)], "title": "Renamed"}
    saved = ok(await client.patch(team.url, json=body, headers=team.admin.headers))
    assert saved["title"] == "Renamed" and saved["assignee_ids"] == [str(team.editor.id)]
    again = ok(await client.get(team.url, headers=team.admin.headers))
    assert again["title"] == "Renamed"
    (note,) = await notes(pg_session_factory, team.editor.id)
    assert note.type is NotificationType.BOARD_CARD_ASSIGNED
    assert await slack.flush() == []
