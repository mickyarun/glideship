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

"""Repo activity edges: retitled, reopened and fork pull requests, and a failure that
never costs the delivery its other work."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1 import github_webhook as gh_webhook
from app.repositories.board_repo_activity import BoardRepoActivityRepository
from app.services import event_bus
from app.services.after_commit import publish_after_commit
from tests.integration.board_repo_activity_support import (
    deliver,
    linked_board,
    pr_body,
    push_body,
    repo_events,
)
from tests.integration.github_webhook_support import WebhookCalls, delivery_row
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration

MARKER = "test_delivery_bookkeeping"


@pytest.fixture(autouse=True)
def calls(monkeypatch: pytest.MonkeyPatch, pg_session_factory: Factory) -> WebhookCalls:
    """Route the endpoint at the test database and record the stream publish."""
    return WebhookCalls.install(monkeypatch, gh_webhook, pg_session_factory)


async def test_a_new_title_links_the_card_and_a_reopen_is_recorded(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    lb = await linked_board(client, pg_session_factory)
    await deliver(client, pr_body(lb.full_name, title="Login"))
    assert await repo_events(client, lb.pm, lb.key, 1) == []

    retitled = f"{lb.key}-1 Login"
    changes = {"title": {"from": "Login"}}
    await deliver(client, pr_body(lb.full_name, title=retitled, action="edited", changes=changes))
    # A body edit, or the same title again, adds nothing.
    await deliver(client, pr_body(lb.full_name, title=retitled, action="edited"))
    await deliver(client, pr_body(lb.full_name, title=retitled, action="edited", changes=changes))
    await deliver(client, pr_body(lb.full_name, title=retitled, action="closed"))
    await deliver(client, pr_body(lb.full_name, title=retitled, action="reopened"))

    kinds = sorted(e["detail"]["kind"] for e in await repo_events(client, lb.pm, lb.key, 1))
    assert kinds == ["pr_closed", "pr_opened", "pr_reopened"]


async def test_a_pull_request_from_a_fork_names_no_card(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    lb = await linked_board(client, pg_session_factory)

    await deliver(client, pr_body(lb.full_name, title=f"{lb.key}-1 spam", fork=True))

    assert await repo_events(client, lb.pm, lb.key, 1) == []


async def test_a_failure_recording_activity_still_answers_200_and_keeps_the_rest(
    client: AsyncClient, pg_session_factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    lb = await linked_board(client, pg_session_factory)
    await deliver(client, pr_body(lb.full_name, title=f"{lb.key}-1 login"))
    heard: list[tuple[str, dict[str, Any]]] = []
    publish = event_bus.publish

    def _publish(topic: str, data: dict[str, Any]) -> None:
        heard.append((topic, data))
        publish(topic, data)

    handled = gh_webhook.handle_github_event

    async def _bookkeeping(**kwargs: Any) -> None:
        # The delivery's own work queues an announcement before repo activity runs.
        await handled(**kwargs)
        db: AsyncSession = kwargs["db"]
        publish_after_commit(db, MARKER, {"delivery": "push"})

    async def _broken(*_args: Any, **_kwargs: Any) -> bool:
        raise RuntimeError("database hiccup")

    monkeypatch.setattr(event_bus, "publish", _publish)
    monkeypatch.setattr(gh_webhook, "handle_github_event", _bookkeeping)
    monkeypatch.setattr(BoardRepoActivityRepository, "add_once", _broken)

    resp = await deliver(client, push_body(lb.full_name, f"{lb.key}-1 wire it"), event="push")

    assert resp.status_code == 200
    assert (MARKER, {"delivery": "push"}) in heard
    assert await delivery_row(pg_session_factory, resp.request.headers["X-GitHub-Delivery"])
    # The earlier pull request is still on the card; the failed push added nothing.
    (event,) = await repo_events(client, lb.pm, lb.key, 1)
    assert event["detail"]["kind"] == "pr_opened"
    assert not [d for t, d in heard if t.startswith("board:")]
