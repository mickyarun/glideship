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

"""CLI flags that take a run's built-in tools away, leaving only its MCP tools.

A run that sets ``ClaudeRunnerConfig.builtin_tools`` (a board card run sets
``[]``) must not reach the host's files, shell or network on its own. For the
Claude CLI that is two layers, both honoured under
``--dangerously-skip-permissions``:

* ``--tools <list>`` names the built-in tools the model is offered at all
  (``""`` offers none; ``--print`` mode only, which the runner always uses).
  MCP tools are not built-ins and stay available.
* ``--disallowedTools`` adds a deny rule for every other built-in tool, the
  same mechanism the inline ``permissions.deny`` list relies on, so a CLI
  build that ignored ``--tools`` still refuses them.

``--allowedTools`` names the granted MCP tools for the record; under the
bypass mode it allows rather than restricts, so it is not relied on.

Copilot gets ``--available-tools`` with its namespaced MCP tool names.
Providers with no such flag are refused by the capability gate instead.
"""

from typing import Final

# Every built-in tool the Claude CLI ships that reads, writes, runs or fetches.
CLAUDE_BUILTIN_TOOLS: Final = (
    "Bash",
    "BashOutput",
    "KillShell",
    "Read",
    "Write",
    "Edit",
    "MultiEdit",
    "NotebookEdit",
    "Glob",
    "Grep",
    "LS",
    "WebFetch",
    "WebSearch",
    "Task",
    "TodoWrite",
    "SlashCommand",
    "Skill",
    "ExitPlanMode",
)
CLAUDE_MCP_PREFIX: Final = "mcp__bodhiorchard__"
COPILOT_MCP_PREFIX: Final = "bodhiorchard-"


def claude_tool_scope_args(builtin_tools: list[str] | None, mcp_tools: list[str]) -> list[str]:
    """``--tools`` / ``--disallowedTools`` / ``--allowedTools`` for a scoped run (else none)."""
    if builtin_tools is None:
        return []
    denied = [t for t in CLAUDE_BUILTIN_TOOLS if t not in builtin_tools]
    args = ["--tools", ",".join(builtin_tools)]
    if denied:
        args += ["--disallowedTools", ",".join(denied)]
    allowed = [*builtin_tools, *(CLAUDE_MCP_PREFIX + t for t in mcp_tools)]
    if allowed:
        args += ["--allowedTools", ",".join(allowed)]
    return args


def copilot_tool_scope_args(builtin_tools: list[str] | None, mcp_tools: list[str]) -> list[str]:
    """``--available-tools`` for a scoped Copilot run (else none)."""
    if builtin_tools is None:
        return []
    names = [*builtin_tools, *(COPILOT_MCP_PREFIX + t for t in mcp_tools)]
    return [f"--available-tools={','.join(names)}"]
