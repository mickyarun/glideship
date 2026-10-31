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

"""The one list of MCP tools a board card run may ever hold, and how a run's tools are picked.

A run's tools are its skill's declared ``mcp_tools`` intersected with
:data:`BOARD_RUN_ALLOWLIST`, plus the two card tools it always has. Nothing on
the list writes outside the run's own card, so a BUD skill picked for a stage
can't change BUDs, features or the org. Within that:

* the engineering read tools (features, bugs, design systems, code graph)
  are dropped unless the person who started the run (the clicker, or the
  person whose move or create started it) holds ``workspace:engineering``;
  a run with nobody behind it gets none;
* the code tools are dropped when the board has no active linked
  repository, and the run's token limits them to those repositories.

``get_team_context`` is left off on purpose: it returns people's emails.
"""

from typing import Final

from app.mcp.token_grants import REPO_SCOPED_TOOLS
from app.services.boards.constants import CARD_RUN_TOOLS

# Org-wide read tools from the engineering workspace.
BOARD_RUN_ENGINEERING_TOOLS: Final = frozenset(
    {
        "get_features",
        "check_feature_exists",
        "search_bugs",
        "list_design_systems",
        "get_design_system",
    }
)
# The code-graph tools, each limited to the board's linked repositories.
BOARD_RUN_CODE_TOOLS: Final = REPO_SCOPED_TOOLS
BOARD_RUN_ALLOWLIST: Final = CARD_RUN_TOOLS | BOARD_RUN_ENGINEERING_TOOLS | BOARD_RUN_CODE_TOOLS


def run_tools(declared: list[str], *, engineering: bool, has_repos: bool) -> frozenset[str]:
    """The tools one run's token covers: the card tools, plus what the skill may have."""
    extra = frozenset(declared) & BOARD_RUN_ALLOWLIST
    if not engineering:
        extra -= BOARD_RUN_ENGINEERING_TOOLS | BOARD_RUN_CODE_TOOLS
    if not has_repos:
        extra -= BOARD_RUN_CODE_TOOLS
    return CARD_RUN_TOOLS | extra
