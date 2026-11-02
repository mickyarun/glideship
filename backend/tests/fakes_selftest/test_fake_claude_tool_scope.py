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

"""The real ``run_claude_code`` command line for a run scoped to its MCP tools."""

from __future__ import annotations

from pathlib import Path

from app.services.claude_runner import ClaudeRunnerConfig, MCPServerConfig, run_claude_code
from tests.fakes.claude_runner import FakeClaudeRunner
from tests.fakes.claude_script import AgentScript


async def test_a_scoped_run_is_spawned_with_no_built_in_tools(
    fake_claude: FakeClaudeRunner, tmp_path: Path
) -> None:
    fake_claude.enqueue(AgentScript.ok("draft"))
    mcp = MCPServerConfig("http://backend", "tok", tool_names=["write_card_doc"])
    config = ClaudeRunnerConfig(timeout_seconds=5, mcp=mcp, builtin_tools=[])

    await run_claude_code("write the PRD", tmp_path, config)

    run = fake_claude.runs[0]
    assert run.flag("--tools") == ""
    denied = (run.flag("--disallowedTools") or "").split(",")
    assert {"Bash", "Read", "WebFetch"} <= set(denied)
    # The bypass flag is still there; --tools and the deny rules hold under it.
    assert "--dangerously-skip-permissions" in run.argv


async def test_an_unscoped_run_keeps_the_default_tools(
    fake_claude: FakeClaudeRunner, tmp_path: Path
) -> None:
    fake_claude.enqueue(AgentScript.ok("spec"))
    await run_claude_code("write the spec", tmp_path, ClaudeRunnerConfig(timeout_seconds=5))
    run = fake_claude.runs[0]
    assert "--tools" not in run.argv and "--disallowedTools" not in run.argv
