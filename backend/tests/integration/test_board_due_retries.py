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


"""Due reminders that fail are retried as a DM only, and orgs fire only in their window."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.config import settings
from app.models.digest_claim import DigestClaim, DigestClaimStatus
from app.models.notification import NotificationType
from app.models.organization import Organization
from app.repositories.board_due import DueOrg
from app.services import slack_dm
from app.services.boards import due_reminders
from tests.integration.board_api_support import CardTeam, card_team, make_card, org_of
from tests.integration.board_notify_support import Slack, fake_slack, link_slack, notes
from tests.integration.scan_features_bugs_support import Factory
from tests.integration.test_board_notify_edges import deactivate

pytestmark = pytest.mark.integration

KOLKATA = {"leave_digest": {"timezone": "Asia/Kolkata"}, "boards": {"due_reminder_time": "08:00"}}
NEW_YORK = {
    "leave_digest": {"timezone": "America/New_York"},
    "boards": {"due_reminder_time": "08:00"},
}
AT = datetime(2031, 6, 2, 3, 0, tzinfo=UTC)  # 08:30 in Kolkata, 23:00 the day before in New York
OVERDUE = "2031-05-30T10:00:00Z"


@pytest.fixture
def slack(monkeypatch: pytest.MonkeyPatch, pg_session_factory: Factory) -> Slack:
    monkeypatch.setattr(due_reminders, "AsyncSessionLocal", pg_session_factory)
    monkeypatch.setattr(settings.boards, "due_reminder_dm_interval_seconds", 0.0)
    return fake_slack(monkeypatch, pg_session_factory)


async def _team(
    client: AsyncClient, factory: Factory, slack: Slack, config: dict[str, Any] = KOLKATA
) -> tuple[CardTeam, DueOrg, dict[uuid.UUID, str]]:
    """A team whose editor has one overdue card, Slack linked, setup DMs cleared."""
    team = await card_team(client, factory)
    org = await org_of(factory, team.admin)
    async with factory() as db:
        row = await db.get(Organization, org)
        assert row is not None
        row.config = config
        await db.commit()
    ids = await link_slack(factory, org, team.editor.id)
    await make_card(
        client, team.admin, team.key, "Late", due_at=OVERDUE, assignee_ids=[str(team.editor.id)]
    )
    await slack.flush()
    slack.posts.clear()
    return team, DueOrg(org_id=org, config=config, policy_timezone=None), ids


async def _claim(factory: Factory, org: uuid.UUID) -> DigestClaim | None:
    async with factory() as db:
        return await db.scalar(select(DigestClaim).where(DigestClaim.org_id == org))


async def _due_count(factory: Factory, user_id: uuid.UUID) -> int:
    return sum(n.type is NotificationType.BOARD_DUE for n in await notes(factory, user_id))


def _slack_fails(monkeypatch: pytest.MonkeyPatch, slack: Slack) -> list[str]:
    """Every post fails (and is counted); returns the channels tried."""
    tried: list[str] = []

    async def _post(_token: str, channel: str, _text: str, **_kw: Any) -> None:
        tried.append(channel)
        return None

    monkeypatch.setattr(slack_dm, "chat_post_message", _post)
    return tried


async def test_a_failed_dm_is_retried_without_a_second_in_app_row_up_to_the_cap(
    client: AsyncClient,
    pg_session_factory: Factory,
    slack: Slack,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings.boards, "due_reminder_max_retries", 2)
    team, org, ids = await _team(client, pg_session_factory, slack)
    tried = _slack_fails(monkeypatch, slack)

    await due_reminders.org_pass(org, AT)
    claim = await _claim(pg_session_factory, org.org_id)
    assert claim is not None and claim.status is DigestClaimStatus.FAILED and claim.attempts == 0
    assert await _due_count(pg_session_factory, team.editor.id) == 1

    for minute in (1, 2, 3, 4):
        await due_reminders.org_pass(org, AT + timedelta(minutes=minute))
    # The first send and two retries; then it stops.
    assert len(tried) == 3
    claim = await _claim(pg_session_factory, org.org_id)
    assert claim is not None and claim.status is DigestClaimStatus.FAILED and claim.attempts == 2
    assert await _due_count(pg_session_factory, team.editor.id) == 1
    assert ids


async def test_a_retry_after_slack_recovers_sends_the_dm_only(
    client: AsyncClient,
    pg_session_factory: Factory,
    slack: Slack,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    team, org, ids = await _team(client, pg_session_factory, slack)
    working = slack_dm.chat_post_message
    _slack_fails(monkeypatch, slack)
    await due_reminders.org_pass(org, AT)
    monkeypatch.setattr(slack_dm, "chat_post_message", working)

    await due_reminders.org_pass(org, AT + timedelta(minutes=1))
    (text,) = slack.to(ids[team.editor.id])
    assert "Late" in text
    claim = await _claim(pg_session_factory, org.org_id)
    assert claim is not None and claim.status is DigestClaimStatus.SENT and claim.attempts == 1
    assert await _due_count(pg_session_factory, team.editor.id) == 1
    await due_reminders.org_pass(org, AT + timedelta(minutes=2))
    assert len(slack.to(ids[team.editor.id])) == 1


async def test_a_claim_left_unfinished_is_taken_back_once_stale(
    client: AsyncClient,
    pg_session_factory: Factory,
    slack: Slack,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    team, org, ids = await _team(client, pg_session_factory, slack)

    async def _crash(*_args: Any, **_kwargs: Any) -> dict[uuid.UUID, bool]:
        raise RuntimeError("the process died mid-send")

    real_send = due_reminders.send_each
    monkeypatch.setattr(due_reminders, "send_each", _crash)
    with pytest.raises(RuntimeError):
        await due_reminders.org_pass(org, AT)
    monkeypatch.setattr(due_reminders, "send_each", real_send)
    claim = await _claim(pg_session_factory, org.org_id)
    assert claim is not None and claim.status is DigestClaimStatus.CLAIMED

    # Fresh: another tick leaves it to whoever holds it.
    await due_reminders.org_pass(org, AT + timedelta(minutes=1))
    assert slack.to(ids[team.editor.id]) == []

    stale = timedelta(minutes=settings.boards.due_reminder_stale_minutes + 1)
    async with pg_session_factory() as db:
        await db.execute(
            update(DigestClaim)
            .where(DigestClaim.id == claim.id)
            .values(updated_at=claim.updated_at - stale)
        )
        await db.commit()
    await due_reminders.org_pass(org, AT + timedelta(minutes=2))
    assert len(slack.to(ids[team.editor.id])) == 1
    claim = await _claim(pg_session_factory, org.org_id)
    assert claim is not None and claim.status is DigestClaimStatus.SENT and claim.attempts == 1
    assert await _due_count(pg_session_factory, team.editor.id) == 1


async def test_a_deactivated_assignee_gets_no_reminder(
    client: AsyncClient, pg_session_factory: Factory, slack: Slack
) -> None:
    team, org, ids = await _team(client, pg_session_factory, slack)
    await deactivate(pg_session_factory, team.editor.id)
    await due_reminders.org_pass(org, AT)
    assert slack.to(ids[team.editor.id]) == []
    assert await _due_count(pg_session_factory, team.editor.id) == 0
    assert await _claim(pg_session_factory, org.org_id) is None


async def test_one_tick_fires_only_the_org_in_its_window(
    client: AsyncClient, pg_session_factory: Factory, slack: Slack
) -> None:
    india, india_org, india_ids = await _team(client, pg_session_factory, slack)
    usa, usa_org, usa_ids = await _team(client, pg_session_factory, slack, NEW_YORK)

    await due_reminders.tick_once(AT)
    assert len(slack.to(india_ids[india.editor.id])) == 1
    assert slack.to(usa_ids[usa.editor.id]) == []
    assert await _claim(pg_session_factory, usa_org.org_id) is None
    assert await _claim(pg_session_factory, india_org.org_id) is not None

    # 08:30 in New York is 12:30 UTC: now it's the other way round.
    await due_reminders.tick_once(AT + timedelta(hours=9, minutes=30))
    assert len(slack.to(usa_ids[usa.editor.id])) == 1
    assert len(slack.to(india_ids[india.editor.id])) == 1
