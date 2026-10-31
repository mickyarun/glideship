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


"""What one piece of repo activity is, and the card keys a text names.

Shared by the pull request and push readers
(:mod:`app.services.boards.repo_activity_pr`,
:mod:`app.services.boards.repo_activity_parse`); no database.
"""

import re
import uuid
from collections.abc import Mapping
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
# GitHub logins: letters, digits and single hyphens, at most 39 characters.
_LOGIN: Final = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?")
REPO_ACTIVITY_TITLE_MAX_CHARS: Final = 200

CardKey = tuple[str, int]


class RepoActivityKind(StrEnum):
    """What happened on the repository."""

    PR_OPENED = "pr_opened"
    PR_REOPENED = "pr_reopened"
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


def mapping_of(value: Any) -> Mapping[str, Any]:
    """``value`` if it is a mapping, else an empty one."""
    return value if isinstance(value, Mapping) else {}


def text_of(value: Any) -> str:
    """``value`` if it is a string, else ``""``."""
    return value if isinstance(value, str) else ""


def login_of(value: Any) -> str | None:
    """``value`` if it is a GitHub login, else None."""
    return value if isinstance(value, str) and _LOGIN.fullmatch(value) else None


def repo_web_url(full_name: str | None) -> str | None:
    """The repository's GitHub page, from its own full name; None for a malformed one."""
    if full_name is None or not GITHUB_FULL_NAME_PATTERN.fullmatch(full_name):
        return None
    return f"{GITHUB_WEB_URL}/{full_name}"
