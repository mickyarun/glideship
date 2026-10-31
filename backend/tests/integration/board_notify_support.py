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

"""Capture what board notifications send: in-app rows, and Slack DMs that never leave.

The Slack client calls are faked at the edge, so the recipient SQL (opt-outs,
permissions, linked accounts) runs for real against the test database.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Coroutine
from dataclasses import dataclass, field
from typing import Any

import pytest
from sqlalchemy import select

from app.models.notification import Notification
from app.models.user import User
from app.services import slack_dm
from app.services.notifications import notice
from tests.integration.leave_slack_support import connect_slack
from tests.integration.scan_features_bugs_support import Factory


@dataclass
class Slack:
    """DMs posted (``(slack user id, text)``) and background sends not yet run."""

    posts: list[tuple[str, str]] = field(default_factory=list)
    pending: list[Coroutine[Any, Any, None]] = field(default_factory=list)

    async def flush(self) -> list[tuple[str, str]]:
        """Run every queued background send; every DM posted so far."""
        while self.pending:
            await asyncio.gather(*self.pending[:])
            self.pending.clear()
        return self.posts

    def to(self, slack_id: str) -> list[str]:
        """The texts DMed to one Slack user."""
        return [text for who, text in self.posts if who == slack_id]


# Every fake made in the current test; the integration conftest flushes them at teardown.
_open_fakes: list[Slack] = []


async def flush_open_fakes() -> None:
    """Run the sends a test left queued, so none is dropped un-awaited; forget the fakes."""
    while _open_fakes:
        slack = _open_fakes.pop()
        while slack.pending:
            queued = slack.pending[:]
            slack.pending.clear()
            # A test may have made a send fail on purpose; it already asserted that.
            await asyncio.gather(*queued, return_exceptions=True)


def fake_slack(monkeypatch: pytest.MonkeyPatch, factory: Factory) -> Slack:
    """Queue notice sends for :meth:`Slack.flush` and record DMs instead of posting them."""
    slack = Slack()
    _open_fakes.append(slack)

    async def _open(_token: str, slack_id: str) -> str:
        return f"D-{slack_id}"

    async def _post(_token: str, channel: str, text: str, **_kw: Any) -> dict[str, Any]:
        slack.posts.append((channel.removeprefix("D-"), text))
        return {"ok": True}

    monkeypatch.setattr(notice, "spawn", slack.pending.append)
    monkeypatch.setattr(slack_dm, "AsyncSessionLocal", factory)
    monkeypatch.setattr(slack_dm, "conversations_open", _open)
    monkeypatch.setattr(slack_dm, "chat_post_message", _post)
    return slack


async def link_slack(factory: Factory, org: uuid.UUID, *people: uuid.UUID) -> dict[uuid.UUID, str]:
    """Connect the org to Slack and link each person; their Slack ids."""
    ids = {who: f"U{uuid.uuid4().hex[:8].upper()}" for who in people}
    await connect_slack(factory, org, ids)
    return ids


async def mute(factory: Factory, user_id: uuid.UUID, category: str) -> None:
    """Turn one notification category off for a person."""
    async with factory() as db:
        user = await db.get(User, user_id)
        assert user is not None
        user.notification_prefs = {category: False}
        await db.commit()


async def notes(factory: Factory, user_id: uuid.UUID) -> list[Notification]:
    """A person's in-app notifications, oldest first."""
    async with factory() as db:
        rows = await db.scalars(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at)
        )
        return list(rows)
