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

"""Card assignments and comments notify the people on the card, never the one acting."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.notification import Notification, NotificationType
from tests.integration.board_api_support import BOARDS, card_team, make_card, ok, org_of
from tests.integration.board_import_support import (
    capture_jobs,
    mapping,
    named,
    new_board,
    parsed,
    save_and_start,
    use_import_storage,
)
from tests.integration.board_notify_support import Slack, fake_slack, link_slack, mute, notes
from tests.integration.board_support import board_key
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration


@pytest.fixture
def slack(monkeypatch: pytest.MonkeyPatch, pg_session_factory: Factory) -> Slack:
    return fake_slack(monkeypatch, pg_session_factory)


async def test_assigning_someone_else_notifies_them_in_app_and_on_slack(
    client: AsyncClient, pg_session_factory: Factory, slack: Slack
) -> None:
    team = await card_team(client, pg_session_factory)
    org = await org_of(pg_session_factory, team.admin)
    ids = await link_slack(pg_session_factory, org, team.editor.id, team.admin.id)
    card = await make_card(
        client, team.admin, team.key, "Fix the build", assignee_ids=[str(team.editor.id)]
    )
    await slack.flush()
    (note,) = await notes(pg_session_factory, team.editor.id)
    assert note.type is NotificationType.BOARD_CARD_ASSIGNED
    assert note.deep_link == f"/boards/{team.key}/cards/{card['number']}"
    assert f"{card['key']} Fix the build" in (note.message or "")
    (dm,) = slack.to(ids[team.editor.id])
    assert f"*{card['key']}* Fix the build" in dm
    assert f"/boards/{team.key}/cards/{card['number']}|Open card>" in dm
    assert slack.to(ids[team.admin.id]) == []
    assert await notes(pg_session_factory, team.admin.id) == []

    # A PATCH that adds someone tells only the newcomer.
    url = f"{BOARDS}/{team.key}/cards/{card['number']}"
    both = [str(team.editor.id), str(team.viewer.id)]
    ok(await client.patch(url, json={"assignee_ids": both}, headers=team.admin.headers))
    await slack.flush()
    assert len(await notes(pg_session_factory, team.editor.id)) == 1
    (viewer_note,) = await notes(pg_session_factory, team.viewer.id)
    assert viewer_note.type is NotificationType.BOARD_CARD_ASSIGNED


async def test_assigning_yourself_is_silent(
    client: AsyncClient, pg_session_factory: Factory, slack: Slack
) -> None:
    team = await card_team(client, pg_session_factory)
    org = await org_of(pg_session_factory, team.admin)
    await link_slack(pg_session_factory, org, team.editor.id)
    card = await make_card(client, team.editor, team.key, assignee_ids=[str(team.editor.id)])
    url = f"{BOARDS}/{team.key}/cards/{card['number']}"
    ok(await client.patch(url, json={"assignee_ids": []}, headers=team.editor.headers))
    mine = [str(team.editor.id)]
    ok(await client.patch(url, json={"assignee_ids": mine}, headers=team.editor.headers))
    assert await slack.flush() == []
    assert await notes(pg_session_factory, team.editor.id) == []


async def test_a_muted_category_keeps_the_in_app_note_but_sends_no_dm(
    client: AsyncClient, pg_session_factory: Factory, slack: Slack
) -> None:
    team = await card_team(client, pg_session_factory)
    org = await org_of(pg_session_factory, team.admin)
    await link_slack(pg_session_factory, org, team.editor.id)
    await mute(pg_session_factory, team.editor.id, "board_cards")
    await make_card(client, team.admin, team.key, assignee_ids=[str(team.editor.id)])
    assert await slack.flush() == []
    assert len(await notes(pg_session_factory, team.editor.id)) == 1


async def test_comments_reach_the_cards_assignees_but_not_the_author(
    client: AsyncClient, pg_session_factory: Factory, slack: Slack
) -> None:
    team = await card_team(client, pg_session_factory)
    org = await org_of(pg_session_factory, team.admin)
    ids = await link_slack(pg_session_factory, org, team.admin.id, team.editor.id, team.viewer.id)
    card = await make_card(
        client, team.editor, team.key, assignee_ids=[str(team.editor.id), str(team.viewer.id)]
    )
    await slack.flush()
    slack.posts.clear()
    comments = f"{BOARDS}/{team.key}/cards/{card['number']}/comments"
    ok(await client.post(comments, json={"body": "Looks good"}, headers=team.editor.headers), 201)
    await slack.flush()

    def kinds(rows: list[Notification]) -> list[NotificationType]:
        return [n.type for n in rows]

    assert NotificationType.BOARD_CARD_COMMENT not in kinds(
        await notes(pg_session_factory, team.editor.id)
    )
    assert kinds(await notes(pg_session_factory, team.viewer.id))[-1] is (
        NotificationType.BOARD_CARD_COMMENT
    )
    # The admin isn't assigned, so a comment isn't theirs to hear about.
    assert await notes(pg_session_factory, team.admin.id) == []
    assert [who for who, _ in slack.posts] == [ids[team.viewer.id]]
    assert "commented on" in slack.posts[0][1]


async def test_an_import_notifies_nobody(
    client: AsyncClient,
    pg_session_factory: Factory,
    slack: Slack,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    use_import_storage(tmp_path, monkeypatch)
    jobs = capture_jobs(pg_session_factory, monkeypatch)
    org = await new_org(pg_session_factory)
    pm = await named(pg_session_factory, org, "Pat Manager", "pm")
    priya = await named(pg_session_factory, org, "Priya Sharma")
    await link_slack(pg_session_factory, org, priya.id)
    session_id = await parsed(client, pm, jobs)
    await save_and_start(client, pm, session_id, mapping(new_board(board_key()), priya=priya.id))
    await jobs.run_all()
    assert slack.pending == [] and await slack.flush() == []
    async with pg_session_factory() as db:
        count = await db.scalar(
            select(func.count()).select_from(Notification).where(Notification.org_id == org)
        )
    assert count == 0
