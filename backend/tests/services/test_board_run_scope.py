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

"""What a board card run may hold: its tool list, its repositories and its token store."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

import app.models  # noqa: F401  # loaded before the boards constants that import them
from app.mcp import token_grants
from app.mcp.grant_tools import scoped_input_schema, visible
from app.mcp.token_grants import (
    OTHER_REPO,
    GrantRepo,
    InternalTokenGrant,
    ScopedTokenLimitError,
    create_scoped_mcp_token,
    scoped_grant,
)
from app.services.boards.agents.tools import (
    BOARD_RUN_ALLOWLIST,
    BOARD_RUN_CODE_TOOLS,
    run_tools,
)
from app.services.boards.constants import CARD_RUN_TOOLS

DECLARED = [
    "get_features",
    "code_query",
    "write_bud",
    "update_bud",
    "get_team_context",
    "create_todo",
]


def test_a_declared_write_tool_is_stripped_from_a_board_run() -> None:
    tools = run_tools(DECLARED, engineering=True, has_repos=True)
    assert tools == CARD_RUN_TOOLS | {"get_features", "code_query"}
    assert "get_team_context" not in BOARD_RUN_ALLOWLIST


def test_a_run_without_engineering_gets_only_the_card_tools() -> None:
    assert run_tools(DECLARED, engineering=False, has_repos=True) == CARD_RUN_TOOLS


def test_a_board_without_repos_gets_no_code_tools() -> None:
    tools = run_tools([*DECLARED, *BOARD_RUN_CODE_TOOLS], engineering=True, has_repos=False)
    assert not tools & BOARD_RUN_CODE_TOOLS and "get_features" in tools


def test_code_tools_only_accept_the_grants_repositories() -> None:
    mine = GrantRepo(id=uuid.uuid4(), name="shop-api")
    grant = InternalTokenGrant(
        org_id=uuid.uuid4(), tools=frozenset({"code_query", "get_features"}), repos=(mine,)
    )
    assert grant.refusal("code_query", {"repo_id": str(mine.id), "query": "x"}) is None
    assert grant.refusal("code_query", {"repo_id": str(uuid.uuid4())}) == OTHER_REPO
    assert grant.refusal("code_query", {"repo_id": "shop-api"}) == OTHER_REPO
    assert grant.refusal("code_query", {}) == OTHER_REPO
    assert grant.refusal("get_features", {"repo_id": "anything"}) is None
    assert grant.refusal("code_context", {"repo_id": str(mine.id)}) is not None
    # An org-wide token (no repos) is not limited.
    assert InternalTokenGrant(org_id=uuid.uuid4()).refusal("code_query", {}) is None


def test_the_tool_list_narrows_repo_id_to_the_grants_repositories() -> None:
    mine = GrantRepo(id=uuid.uuid4(), name="shop-api")
    grant = InternalTokenGrant(org_id=uuid.uuid4(), tools=frozenset({"code_query"}), repos=(mine,))
    schema = {"type": "object", "properties": {"repo_id": {"type": "string"}}}
    scoped = scoped_input_schema("code_query", schema, grant)
    assert scoped["properties"]["repo_id"]["enum"] == [str(mine.id)]
    assert "shop-api" in scoped["properties"]["repo_id"]["description"]
    assert schema["properties"]["repo_id"] == {"type": "string"}  # the shared one is untouched
    assert scoped_input_schema("code_query", schema, None) is schema
    assert visible("code_query", grant) and not visible("write_bud", grant)


def test_live_tokens_are_never_evicted_and_new_ones_are_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(token_grants, "_scoped_tokens", {})
    org = uuid.uuid4()
    soon = datetime.now(UTC) + timedelta(minutes=5)
    live = [
        create_scoped_mcp_token(InternalTokenGrant(org_id=org, expires_at=soon), limit=2)
        for _ in range(2)
    ]
    with pytest.raises(ScopedTokenLimitError):
        create_scoped_mcp_token(InternalTokenGrant(org_id=org, expires_at=soon), limit=2)
    assert all(scoped_grant(t) is not None for t in live)


def test_expired_tokens_make_room(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(token_grants, "_scoped_tokens", {})
    org = uuid.uuid4()
    past = datetime.now(UTC) - timedelta(seconds=1)
    create_scoped_mcp_token(InternalTokenGrant(org_id=org, expires_at=past), limit=1)
    fresh = create_scoped_mcp_token(InternalTokenGrant(org_id=org), limit=1)
    assert scoped_grant(fresh) is not None and len(token_grants._scoped_tokens) == 1


def test_scoped_calls_name_their_run_and_card_for_the_audit_log() -> None:
    run, card = uuid.uuid4(), uuid.uuid4()
    grant = InternalTokenGrant(org_id=uuid.uuid4(), run_id=run, card_id=card)
    assert grant.audit_fields() == {"grant_run_id": str(run), "grant_card_id": str(card)}
    assert InternalTokenGrant(org_id=uuid.uuid4()).audit_fields() == {}
