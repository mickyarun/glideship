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


"""Pull request deliveries as repo activity, without touching the database.

A pull request is matched on its title and head branch, when it is opened,
reopened, closed or retitled (``edited`` with a title change, recorded as
the state it is in now, so a card the new title names is linked). A pull
request from a fork is ignored unless ``repo_activity_fork_prs`` is on:
anyone can open one naming any card key.
"""

from collections.abc import Mapping
from typing import Any

from app.config import settings
from app.services.boards.repo_activity_types import (
    REPO_ACTIVITY_TITLE_MAX_CHARS,
    RepoActivity,
    RepoActivityKind,
    card_keys,
    login_of,
    mapping_of,
    text_of,
)


def _pr_state(pr: Mapping[str, Any]) -> RepoActivityKind:
    """The pull request as it stands: open, merged or closed."""
    if pr.get("state") != "closed":
        return RepoActivityKind.PR_OPENED
    return RepoActivityKind.PR_MERGED if pr.get("merged") is True else RepoActivityKind.PR_CLOSED


def _pr_kind(payload: Mapping[str, Any], pr: Mapping[str, Any]) -> RepoActivityKind | None:
    action = payload.get("action")
    if action == "opened":
        return RepoActivityKind.PR_OPENED
    if action == "reopened":
        return RepoActivityKind.PR_REOPENED
    if action == "closed":
        return (
            RepoActivityKind.PR_MERGED if pr.get("merged") is True else RepoActivityKind.PR_CLOSED
        )
    # A new title can name a card: link it as the pull request is now.
    if action == "edited" and "title" in mapping_of(payload.get("changes")):
        return _pr_state(pr)
    return None


def _from_this_repo(pr: Mapping[str, Any]) -> bool:
    """True when the head branch lives in the pull request's own repository, not a fork.

    Compared by GitHub's repository id, which survives renames; a fork that
    was deleted has no head repository and doesn't count.
    """
    head = mapping_of(mapping_of(pr.get("head")).get("repo")).get("id")
    base = mapping_of(mapping_of(pr.get("base")).get("repo")).get("id")
    return isinstance(head, int) and not isinstance(head, bool) and head == base


def pull_request(payload: Mapping[str, Any], web: str | None) -> RepoActivity | None:
    """The delivery's pull request change, if it names a card and comes from this repo."""
    pr = mapping_of(payload.get("pull_request"))
    if not settings.boards.repo_activity_fork_prs and not _from_this_repo(pr):
        return None
    kind = _pr_kind(payload, pr)
    number = pr.get("number")
    if kind is None or not isinstance(number, int) or isinstance(number, bool) or number <= 0:
        return None
    title = text_of(pr.get("title"))
    keys = card_keys(title, text_of(mapping_of(pr.get("head")).get("ref")))
    if not keys:
        return None
    return RepoActivity(
        kind=kind,
        external_id=str(number),
        ref=f"#{number}",
        url=f"{web}/pull/{number}" if web else None,
        title=title[:REPO_ACTIVITY_TITLE_MAX_CHARS],
        author_login=login_of(mapping_of(pr.get("user")).get("login")),
        keys=keys,
    )
