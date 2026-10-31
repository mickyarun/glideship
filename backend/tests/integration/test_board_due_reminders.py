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

"""The morning due reminder: once per person per day, open cards only, in the org's time."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.digest_claim import DigestClaim, DigestClaimStatus
from app.models.notification import Notification, NotificationType
from app.models.organization import Organization
from app.services.boards import due_reminders
from tests.integration.board_api_support import (
    BOARDS,
    Person,
    card_team,
    make_board,
    make_card,
    ok,
    org_of,
    put_role,
    stage_id,
)
from tests.integration.board_notify_support import Slack, fake_slack, link_slack, mute, notes
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration

# Kolkata is UTC+5:30 with no DST: 03:00 UTC is 08:30 there.
CONFIG = {"leave_digest": {"timezone": "Asia/Kolkata"}, "boards": {"due_reminder_time": "08:00"}}
BEFORE = datetime(2030, 3, 4, 2, 29, tzinfo=UTC)  # 07:59 local
AT = datetime(2030, 3, 4, 3, 0, tzinfo=UTC)  # 08:30 local
LATER = datetime(2030, 3, 4, 3, 1, tzinfo=UTC)


@pytest.fixture
def slack(monkeypatch: pytest.MonkeyPatch, pg_session_factory: Factory) -> Slack:
    monkeypatch.setattr(due_reminders, "AsyncSessionLocal", pg_session_factory)
    return fake_slack(monkeypatch, pg_session_factory)


async def _configure(factory: Factory, org: uuid.UUID) -> dict[str, Any]:
    async with factory() as db:
        organization = await db.get(Organization, org)
        assert organization is not None
        organization.config = CONFIG
        await db.commit()
    return CONFIG


async def _card(
    client: AsyncClient, who: Person, key: str, title: str, due: str, *people: Person
) -> dict[str, Any]:
    return await make_card(
        client, who, key, title, due_at=due, assignee_ids=[str(p.id) for p in people]
    )


async def _due_notes(factory: Factory, user_id: uuid.UUID) -> list[Notification]:
    return [n for n in await notes(factory, user_id) if n.type is NotificationType.BOARD_DUE]


async def _settled(slack: Slack) -> None:
    """Send and forget the assignment DMs the setup caused."""
    await slack.flush()
    slack.posts.clear()


async def _claims(factory: Factory, org: uuid.UUID) -> list[DigestClaim]:
    async with factory() as db:
        return list(await db.scalars(select(DigestClaim).where(DigestClaim.org_id == org)))


async def test_one_reminder_per_person_per_day_with_only_open_cards(
    client: AsyncClient, pg_session_factory: Factory, slack: Slack
) -> None:
    team = await card_team(client, pg_session_factory)
    org = await org_of(pg_session_factory, team.admin)
    config = await _configure(pg_session_factory, org)
    ids = await link_slack(pg_session_factory, org, team.editor.id, team.viewer.id)
    key, ed, vw = team.key, team.editor, team.viewer
    # 00:30 local on the 4th: due today there, though it was the 3rd in UTC.
    await _card(client, team.admin, key, "Early today", "2030-03-03T19:00:00Z", ed)
    await _card(client, team.admin, key, "Late", "2030-03-02T10:00:00Z", ed, vw)
    await _card(client, team.admin, key, "Tonight", "2030-03-04T12:00:00Z", ed)
    # 00:30 local on the 5th: tomorrow.
    await _card(client, team.admin, key, "Tomorrow", "2030-03-04T19:00:00Z", ed)
    done = await _card(client, team.admin, key, "Finished", "2030-03-02T10:00:00Z", ed)
    board = ok(await client.get(f"{BOARDS}/{key}", headers=team.admin.headers))
    url = f"{BOARDS}/{key}/cards"
    move = {"stage_id": stage_id(board, "Done")}
    ok(await client.post(f"{url}/{done['number']}/move", json=move, headers=ed.headers))
    gone = await _card(client, team.admin, key, "Archived", "2030-03-02T10:00:00Z", ed)
    ok(await client.post(f"{url}/{gone['number']}/archive", headers=ed.headers))
    ticked = await _card(client, team.admin, key, "Ticked", "2030-03-02T10:00:00Z", ed)
    patch = {"due_done": True}
    ok(await client.patch(f"{url}/{ticked['number']}", json=patch, headers=ed.headers))

    await _settled(slack)
    await due_reminders.org_pass(org, config, BEFORE)
    assert await slack.flush() == [] and await _claims(pg_session_factory, org) == []

    await due_reminders.org_pass(org, config, AT)
    (text,) = slack.to(ids[ed.id])
    overdue, today = text.split("*Due today*")
    assert "Late" in overdue and "Early today" not in overdue
    assert "Early today" in today and "Tonight" in today
    for skipped in ("Tomorrow", "Finished", "Archived", "Ticked"):
        assert skipped not in text
    (viewer_text,) = slack.to(ids[vw.id])
    assert "Late" in viewer_text and "*Due today*" not in viewer_text
    (note,) = await _due_notes(pg_session_factory, ed.id)
    assert note.message == "You have 1 card overdue and 2 cards due today."

    # A second tick, and a restart (a fresh pass reads only the database).
    await due_reminders.org_pass(org, config, LATER)
    await due_reminders.org_pass(org, config, AT)
    assert len(slack.posts) == 2
    assert len(await _due_notes(pg_session_factory, ed.id)) == 1
    claims = await _claims(pg_session_factory, org)
    assert sorted(c.user_id for c in claims) == sorted([ed.id, vw.id])
    assert {c.status for c in claims} == {DigestClaimStatus.SENT}


async def test_lost_access_archived_boards_and_muting(
    client: AsyncClient, pg_session_factory: Factory, slack: Slack
) -> None:
    team = await card_team(client, pg_session_factory)
    org = await org_of(pg_session_factory, team.admin)
    config = await _configure(pg_session_factory, org)
    ids = await link_slack(pg_session_factory, org, team.editor.id, team.viewer.id)
    await _card(client, team.admin, team.key, "Kept", "2030-03-02T10:00:00Z", team.viewer)
    await _card(client, team.admin, team.key, "Mine", "2030-03-02T10:00:00Z", team.editor)
    other = (await make_board(client, team.admin, visibility="members"))["board"]["key"]
    await put_role(client, team.admin, other, team.editor.id, "editor")
    await _card(client, team.admin, other, "Shelved", "2030-03-02T10:00:00Z", team.editor)
    ok(await client.post(f"{BOARDS}/{other}/archive", headers=team.admin.headers))
    remove = f"{BOARDS}/{team.key}/members/{team.viewer.id}"
    ok(await client.delete(remove, headers=team.admin.headers))
    await mute(pg_session_factory, team.editor.id, "board_due_reminders")

    await _settled(slack)
    await due_reminders.org_pass(org, config, AT)
    assert await slack.flush() == []
    assert ids  # both linked; neither should hear on Slack
    # The viewer can't open the board any more: nothing at all.
    assert await _due_notes(pg_session_factory, team.viewer.id) == []
    # Muted: the in-app note only, about the active board's card.
    (note,) = await _due_notes(pg_session_factory, team.editor.id)
    assert note.message == "You have 1 card overdue."
    (claim,) = await _claims(pg_session_factory, org)
    assert claim.user_id == team.editor.id and claim.status is DigestClaimStatus.SKIPPED
