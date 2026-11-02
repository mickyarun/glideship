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

"""Taking built-in tools away from a run: the CLI flags, and providers that can't."""

from __future__ import annotations

import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.mcp import token_grants
from app.mcp.token_grants import InternalTokenGrant, create_scoped_mcp_token
from app.models.organization import AIProvider
from app.services.ai_runner import ollama_tools
from app.services.ai_runner.capabilities import CAPABILITIES
from app.services.ai_runner.capability_gate import unsupported_reason
from app.services.ai_runner.ollama_provider import OllamaProvider
from app.services.claude_guard.tool_scope import (
    claude_tool_scope_args,
    copilot_tool_scope_args,
)
from app.services.claude_runner import NO_REPO_CONTEXT, ClaudeRunnerConfig, MCPServerConfig


def test_a_scoped_claude_run_has_no_built_in_tools() -> None:
    args = claude_tool_scope_args([], ["write_card_doc", "get_card_context"])
    assert args[:2] == ["--tools", ""]
    denied = args[args.index("--disallowedTools") + 1].split(",")
    assert {"Bash", "Read", "Write", "Edit", "WebFetch", "WebSearch", "Glob", "Grep"} <= set(
        denied
    )
    assert {"Task", "NotebookEdit"} <= set(denied)
    allowed = args[args.index("--allowedTools") + 1].split(",")
    assert allowed == ["mcp__bodhiorchard__write_card_doc", "mcp__bodhiorchard__get_card_context"]


def test_an_unscoped_run_keeps_the_cli_defaults() -> None:
    assert claude_tool_scope_args(None, ["write_bud"]) == []
    assert copilot_tool_scope_args(None, ["write_bud"]) == []


def test_a_scoped_copilot_run_offers_only_its_mcp_tools() -> None:
    assert copilot_tool_scope_args([], ["write_card_doc"]) == [
        "--available-tools=bodhiorchard-write_card_doc"
    ]


def test_a_provider_that_cannot_drop_its_tools_refuses_a_scoped_run() -> None:
    scoped = ClaudeRunnerConfig(builtin_tools=[])
    assert unsupported_reason(CAPABILITIES[AIProvider.codex], NO_REPO_CONTEXT, scoped)
    assert unsupported_reason(CAPABILITIES[AIProvider.claude], NO_REPO_CONTEXT, scoped) is None
    plain = ClaudeRunnerConfig()
    assert unsupported_reason(CAPABILITIES[AIProvider.codex], NO_REPO_CONTEXT, plain) is None


def _auth(grant: InternalTokenGrant | None) -> Any:
    auth = MagicMock()
    auth.grant = grant
    return auth


@pytest.fixture(autouse=True)
def _quiet(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    audit = MagicMock()
    monkeypatch.setattr(ollama_tools, "emit_audit", audit)
    monkeypatch.setattr(token_grants, "_scoped_tokens", {})
    return audit


async def test_ollama_refuses_a_tool_it_was_not_given(_quiet: MagicMock) -> None:
    handler = AsyncMock(return_value={"ok": True})
    with patch.dict(ollama_tools.TOOL_HANDLERS, {"get_features": handler}):
        out = await ollama_tools.dispatch_tool(
            MagicMock(), _auth(None), "get_features", {}, allowed={"write_card_doc"}
        )
    assert "not given" in json.loads(out)["error"]
    handler.assert_not_awaited()
    assert _quiet.call_args.kwargs["status_code"] == 403


async def test_ollama_fails_closed_once_the_runs_token_is_gone() -> None:
    grant = InternalTokenGrant(org_id=uuid.uuid4(), tools=frozenset({"get_features"}))
    token = create_scoped_mcp_token(grant, limit=5)
    handler = AsyncMock(return_value={"ok": True})
    with patch.dict(ollama_tools.TOOL_HANDLERS, {"get_features": handler}):
        live = await ollama_tools.dispatch_tool(
            MagicMock(), _auth(grant), "get_features", {}, allowed={"get_features"}, token=token
        )
        token_grants.revoke_scoped_mcp_token(token)
        gone = await ollama_tools.dispatch_tool(
            MagicMock(), _auth(grant), "get_features", {}, allowed={"get_features"}, token=token
        )
    assert json.loads(live) == {"ok": True}
    assert "ended" in json.loads(gone)["error"]
    handler.assert_awaited_once()


async def test_an_ollama_run_whose_scoped_token_is_gone_never_starts() -> None:
    grant = InternalTokenGrant(org_id=uuid.uuid4(), tools=frozenset({"write_card_doc"}))
    mcp = MCPServerConfig(
        backend_url="http://b",
        mcp_token="evicted",
        tool_names=["write_card_doc"],
        org_id=str(grant.org_id),
        grant=grant,
    )
    chat = AsyncMock()
    env = {"OLLAMA_HOST": "http://ollama:11434", "OLLAMA_MODEL": "qwen3:latest"}
    with patch("app.services.ai_runner.ollama_provider.chat", chat):
        result = await OllamaProvider().run(
            "q", NO_REPO_CONTEXT, ClaudeRunnerConfig(mcp=mcp, env_extra=env)
        )
    assert result.success is False and "ended" in (result.error or "")
    chat.assert_not_awaited()
