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

"""Which entries start ``on_enter`` agents, and what a run's token grant allows."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from app.mcp import token_grants
from app.mcp.token_grants import (
    InternalTokenGrant,
    create_scoped_mcp_token,
    require_tool_grant,
    revoke_scoped_mcp_token,
    scoped_grant,
)
from app.services.boards.constants import CARD_RUN_READ_TOOLS, CARD_RUN_TOOLS
from app.services.boards.move_rules import ENTRY_RULES, EntryCause


def test_only_chosen_moves_and_creates_start_on_enter_agents() -> None:
    starts = {cause for cause, rules in ENTRY_RULES.items() if rules.on_enter_agents}
    assert starts == {EntryCause.MOVE, EntryCause.MOVE_BOARD, EntryCause.CREATE}
    assert set(ENTRY_RULES) == set(EntryCause)


def test_a_handover_checks_entry_rules_but_starts_no_agent() -> None:
    rules = ENTRY_RULES[EntryCause.HANDOVER]
    assert (rules.required_fields, rules.open_checklist, rules.on_enter_agents) == (
        True,
        True,
        False,
    )


def test_the_run_tools_never_include_a_write_outside_the_card() -> None:
    assert {"write_card_doc", "get_card_context"} == CARD_RUN_TOOLS
    assert not any(
        tool.startswith(("write_", "update_", "create_")) for tool in CARD_RUN_READ_TOOLS
    )


def test_a_scoped_grant_allows_only_its_tools() -> None:
    grant = InternalTokenGrant(org_id=uuid.uuid4(), tools=frozenset({"write_card_doc"}))
    assert grant.allows("write_card_doc") and not grant.allows("write_bud")
    assert InternalTokenGrant(org_id=uuid.uuid4()).allows("write_bud")


def _auth(grant: InternalTokenGrant | None) -> Any:
    return SimpleNamespace(grant=grant, org_id=uuid.uuid4())


def test_require_tool_grant_refuses_tools_outside_it() -> None:
    grant = InternalTokenGrant(org_id=uuid.uuid4(), tools=frozenset({"get_card_context"}))
    require_tool_grant(_auth(grant), "get_card_context")
    require_tool_grant(_auth(None), "write_bud")
    with pytest.raises(HTTPException) as refused:
        require_tool_grant(_auth(grant), "write_bud")
    assert refused.value.status_code == 403


def test_scoped_tokens_expire_and_can_be_revoked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(token_grants, "_scoped_tokens", {})
    org = uuid.uuid4()
    live = create_scoped_mcp_token(
        InternalTokenGrant(org_id=org, expires_at=datetime.now(UTC) + timedelta(minutes=5))
    )
    stale = create_scoped_mcp_token(
        InternalTokenGrant(org_id=org, expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    assert scoped_grant(live) is not None
    assert scoped_grant(stale) is None
    revoke_scoped_mcp_token(live)
    assert scoped_grant(live) is None
    assert token_grants._scoped_tokens == {}
