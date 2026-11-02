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


"""Card keys and repo activity read out of GitHub deliveries, without a database."""

from typing import Any

import pytest

from app.config import settings
from app.services.boards.repo_activity_parse import activities
from app.services.boards.repo_activity_types import RepoActivityKind, card_keys

FULL = "acme/api"
REPO_ID = 41
FORK_ID = 99


def _pr(
    action: str,
    *,
    merged: bool = False,
    title: str = "Fix",
    ref: str = "main",
    state: str | None = None,
    head_repo: Any = REPO_ID,
    **extra: Any,
) -> Any:
    head: dict[str, Any] = {"ref": ref}
    if head_repo is not None:
        head["repo"] = {"id": head_repo, "full_name": FULL if head_repo == REPO_ID else "x/api"}
    return {
        "action": action,
        "pull_request": {
            "number": 7,
            "title": title,
            "merged": merged,
            "state": state or ("closed" if action == "closed" else "open"),
            "head": head,
            "base": {"ref": "main", "repo": {"id": REPO_ID, "full_name": FULL}},
            "user": {"login": "octo-cat"},
            "html_url": "https://evil.example/pull/7",
        },
        **extra,
    }


@pytest.mark.parametrize(
    ("text", "keys"),
    [
        ("OPS-12 fix login", {("OPS", 12)}),
        ("fix ops-12 and Seo-3", {("OPS", 12), ("SEO", 3)}),
        ("feature/ops-12-login", {("OPS", 12)}),
        ("feat_OPS-12", {("OPS", 12)}),
        ("see:OPS-12.", {("OPS", 12)}),
        ("OPS-12a", set()),
        ("1OPS-12", set()),
        ("O-12", set()),
        ("OPS-0", set()),
        ("OPS-99999999999", set()),
        ("ABCDEFGHIJK-1", set()),
    ],
)
def test_card_keys_are_whole_words_in_any_case(text: str, keys: set[tuple[str, int]]) -> None:
    assert card_keys(text) == keys


def test_card_keys_are_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings.boards, "repo_activity_max_keys", 2)
    assert len(card_keys("AA-1 AA-2 AA-3 AA-4")) == 2


@pytest.mark.parametrize(
    ("action", "merged", "kind"),
    [
        ("opened", False, RepoActivityKind.PR_OPENED),
        ("closed", True, RepoActivityKind.PR_MERGED),
        ("closed", False, RepoActivityKind.PR_CLOSED),
    ],
)
def test_a_pull_request_matches_on_its_title(
    action: str, merged: bool, kind: RepoActivityKind
) -> None:
    (found,) = activities("pull_request", _pr(action, merged=merged, title="OPS-4 login"), FULL)
    assert found.kind is kind
    assert found.keys == {("OPS", 4)}
    assert (found.ref, found.external_id, found.author_login) == ("#7", "7", "octo-cat")
    # Built from the repository's own name, never the payload's link.
    assert found.url == "https://github.com/acme/api/pull/7"


def test_a_pull_request_matches_on_its_branch_and_truncates_its_title() -> None:
    (found,) = activities("pull_request", _pr("opened", title="x" * 500, ref="ops-9-x"), FULL)
    assert found.keys == {("OPS", 9)}
    assert len(found.title) == 200


@pytest.mark.parametrize("action", ["synchronize", "labeled", "assigned"])
def test_other_pull_request_actions_are_ignored(action: str) -> None:
    assert activities("pull_request", _pr(action, title="OPS-4"), FULL) == []


def test_a_reopened_pull_request_is_its_own_activity() -> None:
    (found,) = activities("pull_request", _pr("reopened", title="OPS-4"), FULL)
    assert (found.kind, found.external_id) == (RepoActivityKind.PR_REOPENED, "7")


@pytest.mark.parametrize(
    ("state", "merged", "kind"),
    [
        ("open", False, RepoActivityKind.PR_OPENED),
        ("closed", True, RepoActivityKind.PR_MERGED),
        ("closed", False, RepoActivityKind.PR_CLOSED),
    ],
)
def test_a_retitled_pull_request_links_as_it_stands(
    state: str, merged: bool, kind: RepoActivityKind
) -> None:
    changes = {"title": {"from": "Fix login"}}
    payload = _pr("edited", title="OPS-4 login", state=state, merged=merged, changes=changes)
    (found,) = activities("pull_request", payload, FULL)
    assert (found.kind, found.keys) == (kind, {("OPS", 4)})


def test_an_edit_that_leaves_the_title_alone_is_ignored() -> None:
    payload = _pr("edited", title="OPS-4", changes={"body": {"from": "old"}})
    assert activities("pull_request", payload, FULL) == []


@pytest.mark.parametrize("head_repo", [FORK_ID, None, "41", True])
def test_a_pull_request_from_a_fork_is_ignored(head_repo: Any) -> None:
    assert (
        activities("pull_request", _pr("opened", title="OPS-4", head_repo=head_repo), FULL) == []
    )


def test_fork_pull_requests_can_be_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings.boards, "repo_activity_fork_prs", True)
    (found,) = activities("pull_request", _pr("opened", title="OPS-4", head_repo=FORK_ID), FULL)
    assert found.keys == {("OPS", 4)}


def test_a_push_reads_at_most_the_commit_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings.boards, "repo_activity_max_commits", 20)
    commits = [{"id": f"{n:040x}", "message": f"OPS-{n + 1}"} for n in range(25)]
    found = activities("push", {"ref": "refs/heads/main", "commits": commits}, FULL)
    assert len(found) == 20
    assert {k for a in found for k in a.keys} == {("OPS", n) for n in range(1, 21)}


def test_a_sha_with_a_trailing_newline_is_not_a_sha() -> None:
    payload = {"ref": "refs/heads/main", "commits": [{"id": "a" * 40 + "\n", "message": "OPS-1"}]}
    assert activities("push", payload, FULL) == []


def test_a_pull_request_naming_no_key_is_ignored() -> None:
    assert activities("pull_request", _pr("opened", title="Fix login"), FULL) == []


def test_a_bad_full_name_gives_no_link() -> None:
    (found,) = activities("pull_request", _pr("opened", title="OPS-4"), "not a/name/x")
    assert found.url is None


def test_a_push_matches_each_commit_message_and_the_branch() -> None:
    sha_a, sha_b, sha_c = "a" * 40, "b" * 40, "c" * 40
    payload = {
        "ref": "refs/heads/seo-2-copy",
        "commits": [
            {"id": sha_a, "message": "OPS-1: first\n\nbody", "author": {"username": "dev"}},
            {"id": sha_b, "message": "no key here", "distinct": True},
            {"id": sha_c, "message": "OPS-1 again", "distinct": False},
            {"id": "not-a-sha", "message": "OPS-1"},
        ],
    }
    first, second = activities("push", payload, FULL)
    assert first.kind is RepoActivityKind.COMMIT
    assert first.keys == {("OPS", 1), ("SEO", 2)}
    assert (first.ref, first.title, first.author_login) == ("aaaaaaa", "OPS-1: first", "dev")
    assert first.url == f"https://github.com/acme/api/commit/{sha_a}"
    assert second.keys == {("SEO", 2)} and second.author_login is None


def test_a_push_to_a_tag_matches_only_its_messages() -> None:
    payload = {"ref": "refs/tags/OPS-3", "commits": [{"id": "d" * 40, "message": "nothing"}]}
    assert activities("push", payload, FULL) == []


def test_other_events_and_malformed_payloads_are_ignored() -> None:
    assert activities("issues", {"action": "opened"}, FULL) == []
    assert activities("push", {"commits": "nope"}, FULL) == []
    assert activities("pull_request", {"action": "opened", "pull_request": []}, FULL) == []
