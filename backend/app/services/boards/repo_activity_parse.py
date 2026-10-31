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


"""Read card keys and repo activity out of a GitHub delivery, without touching the database.

A key is a board key and a number (``OPS-12``), matched case-insensitively
and only as a whole word, so ``xOPS-12`` and ``OPS-123a`` don't match. A
pull request is matched on its title and head branch; a push matches each
commit's message and the branch it was pushed to. Links are built from the
repository's own full name, never taken from the payload.
"""

import re
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from app.config import settings
from app.models.board_card import INT4_MAX
from app.services.boards.constants import (
    BOARD_KEY_MAX_LENGTH,
    BOARD_KEY_MIN_LENGTH,
    GITHUB_FULL_NAME_PATTERN,
    GITHUB_WEB_URL,
)

CARD_KEY_IN_TEXT: Final = re.compile(
    rf"(?<![A-Za-z0-9])([A-Za-z]{{{BOARD_KEY_MIN_LENGTH},{BOARD_KEY_MAX_LENGTH}}})-(\d{{1,10}})"
    r"(?![A-Za-z0-9])"
)
_SHA: Final = re.compile(r"^[0-9a-f]{7,40}$")
# GitHub logins: letters, digits and single hyphens, at most 39 characters.
_LOGIN: Final = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
_BRANCH_PREFIX: Final = "refs/heads/"
REPO_ACTIVITY_TITLE_MAX_CHARS: Final = 200
SHORT_SHA_LENGTH: Final = 7

CardKey = tuple[str, int]


class RepoActivityKind(StrEnum):
    """What happened on the repository."""

    PR_OPENED = "pr_opened"
    PR_MERGED = "pr_merged"
    PR_CLOSED = "pr_closed"
    COMMIT = "commit"


@dataclass(frozen=True)
class RepoActivity:
    """One pull request change or commit, and the card keys it names."""

    kind: RepoActivityKind
    external_id: str
    ref: str
    url: str | None
    title: str
    author_login: str | None
    keys: frozenset[CardKey]

    def external_ref(self, repo_id: uuid.UUID) -> str:
        """The idempotency key for this activity on a card."""
        return f"{repo_id}:{self.kind.value}:{self.external_id}"

    def detail(self, repo_id: uuid.UUID) -> dict[str, Any]:
        """The card event's ``detail``."""
        return {
            "repo_id": str(repo_id),
            "kind": self.kind.value,
            "ref": self.ref,
            "url": self.url,
            "title": self.title,
            "author_login": self.author_login,
        }


def card_keys(*texts: str | None) -> frozenset[CardKey]:
    """Every card key the texts name, upper-cased, at most ``repo_activity_max_keys``."""
    found: dict[CardKey, None] = {}
    for text in texts:
        for match in CARD_KEY_IN_TEXT.finditer(text or ""):
            number = int(match.group(2))
            if 0 < number <= INT4_MAX:
                found.setdefault((match.group(1).upper(), number), None)
    return frozenset(list(found)[: settings.boards.repo_activity_max_keys])


def activities(
    event_type: str, payload: Mapping[str, Any], full_name: str | None
) -> list[RepoActivity]:
    """The repo activity in one delivery that names at least one card key."""
    web = _repo_web_url(full_name)
    if event_type == "pull_request":
        found = _pull_request(payload, web)
        return [found] if found is not None else []
    if event_type == "push":
        return list(_push(payload, web))
    return []


def _repo_web_url(full_name: str | None) -> str | None:
    if full_name is None or not GITHUB_FULL_NAME_PATTERN.fullmatch(full_name):
        return None
    return f"{GITHUB_WEB_URL}/{full_name}"


def _pr_kind(payload: Mapping[str, Any], pr: Mapping[str, Any]) -> RepoActivityKind | None:
    action = payload.get("action")
    if action == "opened":
        return RepoActivityKind.PR_OPENED
    if action == "closed":
        return (
            RepoActivityKind.PR_MERGED if pr.get("merged") is True else RepoActivityKind.PR_CLOSED
        )
    return None


def _pull_request(payload: Mapping[str, Any], web: str | None) -> RepoActivity | None:
    pr = _mapping(payload.get("pull_request"))
    kind = _pr_kind(payload, pr)
    number = pr.get("number")
    if kind is None or not isinstance(number, int) or isinstance(number, bool) or number <= 0:
        return None
    title = _text(pr.get("title"))
    keys = card_keys(title, _text(_mapping(pr.get("head")).get("ref")))
    if not keys:
        return None
    return RepoActivity(
        kind=kind,
        external_id=str(number),
        ref=f"#{number}",
        url=f"{web}/pull/{number}" if web else None,
        title=title[:REPO_ACTIVITY_TITLE_MAX_CHARS],
        author_login=_login(_mapping(pr.get("user")).get("login")),
        keys=keys,
    )


def _push(payload: Mapping[str, Any], web: str | None) -> Iterable[RepoActivity]:
    ref = _text(payload.get("ref"))
    branch_keys = (
        card_keys(ref.removeprefix(_BRANCH_PREFIX))
        if ref.startswith(_BRANCH_PREFIX)
        else frozenset()
    )
    commits = payload.get("commits")
    if not isinstance(commits, list):
        return
    for raw in commits[: settings.boards.repo_activity_max_commits]:
        commit = _mapping(raw)
        sha = _text(commit.get("id")).lower()
        # A commit already pushed to another branch isn't new work here.
        if not _SHA.match(sha) or commit.get("distinct") is False:
            continue
        message = _text(commit.get("message"))[: settings.boards.repo_activity_scan_chars]
        keys = frozenset(
            list(branch_keys | card_keys(message))[: settings.boards.repo_activity_max_keys]
        )
        if not keys:
            continue
        yield RepoActivity(
            kind=RepoActivityKind.COMMIT,
            external_id=sha,
            ref=sha[:SHORT_SHA_LENGTH],
            url=f"{web}/commit/{sha}" if web else None,
            title=message.split("\n", 1)[0][:REPO_ACTIVITY_TITLE_MAX_CHARS],
            author_login=_login(_mapping(commit.get("author")).get("username")),
            keys=keys,
        )


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _login(value: Any) -> str | None:
    return value if isinstance(value, str) and _LOGIN.match(value) else None
