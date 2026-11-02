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


"""Pull requests and commits that name a card's key show up in the card's activity.

The real webhook route runs against Postgres; the Redis stream publish is
replaced by a recorder and nothing talks to GitHub.
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from app.api.v1 import github_webhook as gh_webhook
from app.services import event_bus
from tests.integration.board_api_support import link_repo, make_board, make_card, ok, person
from tests.integration.board_move_board_support import move_board
from tests.integration.board_repo_activity_support import (
    deliver,
    linked_board,
    pr_body,
    push_body,
    repo_events,
)
from tests.integration.github_webhook_support import WebhookCalls
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def calls(monkeypatch: pytest.MonkeyPatch, pg_session_factory: Factory) -> WebhookCalls:
    """Route the endpoint at the test database and record the stream publish."""
    return WebhookCalls.install(monkeypatch, gh_webhook, pg_session_factory)


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    """Every event-bus message published while the test runs, on any topic."""
    heard: list[tuple[str, dict[str, Any]]] = []
    publish = event_bus.publish

    def _publish(topic: str, data: dict[str, Any]) -> None:
        heard.append((topic, data))
        publish(topic, data)

    monkeypatch.setattr(event_bus, "publish", _publish)
    return heard


async def test_a_pull_request_title_lands_on_the_card_and_its_board_hears_it(
    client: AsyncClient, pg_session_factory: Factory, sent: list[tuple[str, dict[str, Any]]]
) -> None:
    lb = await linked_board(client, pg_session_factory, visibility="members")
    sent.clear()

    await deliver(client, pr_body(lb.full_name, title=f"{lb.key.lower()}-1: fix login"))

    (event,) = await repo_events(client, lb.pm, lb.key, 1)
    assert event["detail"] == {
        "repo_id": str(lb.repo),
        "kind": "pr_opened",
        "ref": "#5",
        "url": f"https://github.com/{lb.full_name}/pull/5",
        "title": f"{lb.key.lower()}-1: fix login",
        "author_login": "octo",
    }
    assert (event["actor_id"], event["actor_label"]) == (None, "octo")
    # Members-only: the card is announced on its board's topic and nowhere else.
    card_topics = {t for t, d in sent if lb.card["id"] in str(d) or lb.key in str(d)}
    assert card_topics == {f"board:{lb.board_id}"}
    (live,) = [d for t, d in sent if t.startswith("board:")]
    assert (live["event"], live["card_id"]) == ("card_activity", lb.card["id"])


async def test_merges_closes_branches_and_commits_are_each_recorded_once(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    lb = await linked_board(client, pg_session_factory)
    branch = f"feature/{lb.key.lower()}-1-login"
    opened = pr_body(lb.full_name, title="Login", branch=branch)
    await deliver(client, opened)
    # GitHub redelivers under a new delivery id: still one event.
    await deliver(client, opened)
    await deliver(
        client, pr_body(lb.full_name, title="Login", branch=branch, action="closed", merged=True)
    )
    await deliver(client, pr_body(lb.full_name, title=f"{lb.key}-1", number=6, action="closed"))
    push = push_body(lb.full_name, f"{lb.key}-1 wire it", "unrelated")
    await deliver(client, push, event="push")
    await deliver(client, push, event="push")

    events = await repo_events(client, lb.pm, lb.key, 1)
    kinds = sorted((e["detail"]["kind"], e["detail"]["ref"]) for e in events)
    commit = next(e for e in events if e["detail"]["kind"] == "commit")
    assert kinds == sorted(
        [
            ("pr_opened", "#5"),
            ("pr_merged", "#5"),
            ("pr_closed", "#6"),
            ("commit", commit["detail"]["ref"]),
        ]
    )
    assert commit["detail"]["title"] == f"{lb.key}-1 wire it"
    assert commit["detail"]["url"].startswith(f"https://github.com/{lb.full_name}/commit/")


async def test_an_old_key_reaches_the_card_on_a_board_that_links_the_repo(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    lb = await linked_board(client, pg_session_factory)
    linked = (await make_board(client, lb.pm, template="blank"))["board"]["key"]
    unlinked = (await make_board(client, lb.pm, template="blank"))["board"]["key"]
    await link_repo(client, lb.pm, linked, lb.repo)
    other = await make_card(client, lb.pm, lb.key, "Other")
    ok(await move_board(client, lb.pm, lb.key, lb.card, linked))
    ok(await move_board(client, lb.pm, lb.key, other, unlinked))

    title = f"{lb.key}-1 and {lb.key}-2"
    await deliver(client, pr_body(lb.full_name, title=title))

    (event,) = await repo_events(client, lb.pm, linked, 1)
    assert event["detail"]["title"] == title
    # The second card now sits on a board that doesn't link the repository.
    assert await repo_events(client, lb.pm, unlinked, 1) == []


async def test_boards_that_dont_link_the_repo_and_other_orgs_hear_nothing(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    unlinked = await linked_board(client, pg_session_factory, link=False)
    other = await linked_board(client, pg_session_factory)
    # The other org's board uses the same key and links its own repository.
    twin = (await make_board(client, other.pm, key=unlinked.key))["board"]["key"]
    await link_repo(client, other.pm, twin, other.repo)
    await make_card(client, other.pm, twin, "Twin")

    await deliver(client, pr_body(unlinked.full_name, title=f"{unlinked.key}-1"))

    assert await repo_events(client, unlinked.pm, unlinked.key, 1) == []
    assert await repo_events(client, other.pm, twin, 1) == []


async def test_a_viewer_who_can_see_the_board_reads_the_activity(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    lb = await linked_board(client, pg_session_factory, visibility="members")
    outsider = await person(pg_session_factory, lb.org)
    await deliver(client, pr_body(lb.full_name, title=f"{lb.key}-1"))

    url = f"/api/v1/boards/{lb.key}/cards/1/events"
    assert (await client.get(url, headers=outsider.headers)).status_code == 404
    assert len(await repo_events(client, lb.pm, lb.key, 1)) == 1
