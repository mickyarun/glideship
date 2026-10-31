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
and only as a whole word, so ``xOPS-12`` and ``OPS-123a`` don't match
(:mod:`.repo_activity_types`). Pull requests are read by
:mod:`.repo_activity_pr`. A push matches each commit's message and the
branch it was pushed to. Links are built from the repository's own full
name, never taken from the payload.
"""

import re
from collections.abc import Iterable, Mapping
from typing import Any, Final

from app.config import settings
from app.services.boards.repo_activity_pr import pull_request
from app.services.boards.repo_activity_types import (
    REPO_ACTIVITY_TITLE_MAX_CHARS,
    RepoActivity,
    RepoActivityKind,
    card_keys,
    login_of,
    mapping_of,
    repo_web_url,
    text_of,
)

_SHA: Final = re.compile(r"[0-9a-f]{7,40}")
_BRANCH_PREFIX: Final = "refs/heads/"
SHORT_SHA_LENGTH: Final = 7


def activities(
    event_type: str, payload: Mapping[str, Any], full_name: str | None
) -> list[RepoActivity]:
    """The repo activity in one delivery that names at least one card key."""
    web = repo_web_url(full_name)
    if event_type == "pull_request":
        found = pull_request(payload, web)
        return [found] if found is not None else []
    if event_type == "push":
        return list(_push(payload, web))
    return []


def _push(payload: Mapping[str, Any], web: str | None) -> Iterable[RepoActivity]:
    ref = text_of(payload.get("ref"))
    branch_keys = (
        card_keys(ref.removeprefix(_BRANCH_PREFIX))
        if ref.startswith(_BRANCH_PREFIX)
        else frozenset()
    )
    commits = payload.get("commits")
    if not isinstance(commits, list):
        return
    for raw in commits[: settings.boards.repo_activity_max_commits]:
        commit = mapping_of(raw)
        sha = text_of(commit.get("id")).lower()
        # A commit already pushed to another branch isn't new work here.
        if not _SHA.fullmatch(sha) or commit.get("distinct") is False:
            continue
        message = text_of(commit.get("message"))[: settings.boards.repo_activity_scan_chars]
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
            author_login=login_of(mapping_of(commit.get("author")).get("username")),
            keys=keys,
        )
