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


"""Signed pull request and push deliveries, and a board linking the delivering repository."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from httpx import AsyncClient, Response

from tests.integration.board_api_support import (
    BOARDS,
    Person,
    link_repo,
    make_board,
    make_card,
    ok,
    person,
)
from tests.integration.github_webhook_support import signed_headers, tracked_repo
from tests.integration.scan_features_bugs_support import Factory

WEBHOOK = "/api/v1/webhooks/github"


@dataclass(frozen=True)
class LinkedBoard:
    """An org tracking one GitHub repository, a board linking it and one card on it."""

    org: uuid.UUID
    repo: uuid.UUID
    full_name: str
    pm: Person
    key: str
    board_id: str
    card: dict[str, Any]


async def linked_board(
    client: AsyncClient, factory: Factory, *, link: bool = True, **board: Any
) -> LinkedBoard:
    """A new org with a tracked repository and a board (linking it unless ``link`` is off)."""
    org, repo, full_name = await tracked_repo(factory)
    pm = await person(factory, org, "pm")
    made = await make_board(client, pm, **board)
    key = made["board"]["key"]
    if link:
        await link_repo(client, pm, key, repo)
    card = await make_card(client, pm, key, "Login")
    return LinkedBoard(org, repo, full_name, pm, key, made["board"]["id"], card)


def pr_body(
    full_name: str,
    *,
    title: str,
    number: int = 5,
    action: str = "opened",
    merged: bool = False,
    branch: str = "topic",
) -> bytes:
    """A ``pull_request`` delivery."""
    pr = {
        "id": 700_000 + number,
        "number": number,
        "title": title,
        "html_url": f"https://github.com/{full_name}/pull/{number}",
        "head": {"ref": branch, "sha": "h" * 40},
        "base": {"ref": "develop", "sha": "b" * 40},
        "state": "closed" if action == "closed" else "open",
        "user": {"login": "octo", "id": 1},
        "merged": merged,
    }
    payload = {"action": action, "repository": {"full_name": full_name}, "pull_request": pr}
    return json.dumps(payload).encode()


def push_body(full_name: str, *messages: str, branch: str = "topic") -> bytes:
    """A ``push`` delivery with one commit per message."""
    commits = [
        {"id": uuid.uuid4().hex + "0" * 8, "message": m, "author": {"username": "dev"}}
        for m in messages
    ]
    payload = {
        "ref": f"refs/heads/{branch}",
        "repository": {"full_name": full_name},
        "commits": commits,
    }
    return json.dumps(payload).encode()


async def deliver(client: AsyncClient, body: bytes, *, event: str = "pull_request") -> Response:
    """POST a signed delivery with a fresh delivery id."""
    headers = signed_headers(body, uuid.uuid4().hex, event=event)
    resp = await client.post(WEBHOOK, content=body, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp


async def repo_events(
    client: AsyncClient, who: Person, key: str, number: int
) -> list[dict[str, Any]]:
    """The card's ``repo_activity`` events, newest first."""
    page = ok(await client.get(f"{BOARDS}/{key}/cards/{number}/events", headers=who.headers))
    return [e for e in page["items"] if e["type"] == "repo_activity"]
