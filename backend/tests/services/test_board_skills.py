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

"""The board skills: they load, they're seeded, and nothing they declare is denied or stripped."""

from __future__ import annotations

import re

import pytest

import app.models  # noqa: F401  # loaded before the boards constants that import them
from app.agents.skill_mapping import AGENT_SKILL_MAP
from app.mcp.server import MCP_TOOLS
from app.models.agent_skill import AgentType
from app.services.boards.agents.tools import BOARD_RUN_ALLOWLIST
from app.services.boards.constants import AGENT_OUTPUT_KINDS, BOARD_AGENT_TYPES
from app.services.claude_guard.deny_rules import INLINE_DENY_LIST
from app.services.claude_guard.tool_scope import CLAUDE_MCP_PREFIX
from app.services.skill_loader import list_available_skills, load_skill

BOARD_SKILLS = {
    AgentType.BOARD_PRD: "board-prd-writer",
    AgentType.BOARD_DESIGN: "board-design-helper",
}
_WHOLE_TOOL = re.compile(r"^(?P<tool>[A-Za-z_]+)(\((\*|:\*)\))?$")


def _blanket_denied() -> set[str]:
    """Tools the inline deny list refuses outright (not only some of their arguments)."""
    return {m["tool"] for rule in INLINE_DENY_LIST if (m := _WHOLE_TOOL.match(rule))}


def test_the_board_skills_are_seeded_by_agent_type() -> None:
    for agent_type, slug in BOARD_SKILLS.items():
        assert AGENT_SKILL_MAP[agent_type.value] == slug
        assert agent_type in BOARD_AGENT_TYPES
    assert AGENT_OUTPUT_KINDS[AgentType.BOARD_PRD].value == "prd"
    assert AGENT_OUTPUT_KINDS[AgentType.BOARD_DESIGN].value == "design_brief"


@pytest.mark.parametrize("slug", sorted(BOARD_SKILLS.values()))
def test_a_board_skill_needs_no_built_in_tools_and_keeps_all_its_mcp_tools(slug: str) -> None:
    skill = load_skill(slug)
    assert skill.tools == []  # board runs get no built-in tools
    assert {"get_card_context", "write_card_doc"} <= set(skill.mcp_tools)
    # Nothing it declares is stripped by the board-run allowlist.
    assert set(skill.mcp_tools) <= BOARD_RUN_ALLOWLIST
    assert set(skill.mcp_tools) <= {t.name for t in MCP_TOOLS}


@pytest.mark.parametrize("slug", list_available_skills())
def test_the_guard_denies_nothing_a_skill_declares(slug: str) -> None:
    skill = load_skill(slug)
    denied = _blanket_denied()
    assert not set(skill.tools) & denied, slug
    assert not {CLAUDE_MCP_PREFIX + t for t in skill.mcp_tools} & set(INLINE_DENY_LIST), slug


def test_the_deny_rule_matcher_reads_whole_tool_rules() -> None:
    assert _WHOLE_TOOL.match("WebFetch") and _WHOLE_TOOL.match("Bash(*)")
    assert not _WHOLE_TOOL.match("Bash(curl:*)") and not _WHOLE_TOOL.match("Read(~/.ssh/**)")
