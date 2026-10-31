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

"""The startup MCP contract check passes for every registered tool.

``app.main``'s lifespan runs :func:`check_mcp_contracts` first and refuses
to boot when it fails; the integration suite never runs the lifespan, so
this keeps a schema/handler drift (a required key a handler reads through a
helper the check can't see) from reaching a deploy.
"""

import pytest

from app.mcp import board_tool_access
from app.mcp.contract_check import _extract_param_reads, check_mcp_contracts
from app.mcp.server import AUTH_TOOL_HANDLERS, MCP_TOOLS


def test_every_mcp_tool_passes_the_startup_contract_check() -> None:
    check_mcp_contracts()


@pytest.mark.parametrize(
    "name",
    [
        "get_board",
        "get_card",
        "create_card",
        "update_card",
        "move_card",
        "comment_card",
        "write_card_doc",
    ],
)
def test_board_tools_read_every_required_key_literally(name: str) -> None:
    (tool,) = [t for t in MCP_TOOLS if t.name == name]
    reads = _extract_param_reads(AUTH_TOOL_HANDLERS[name])
    assert reads is not None
    assert set(tool.input_schema.get("required") or []) <= reads


def test_the_board_param_helper_takes_a_value_not_a_name() -> None:
    assert board_tool_access.stripped("  OPS-1 ") == "OPS-1"
    assert board_tool_access.stripped(None) == ""
    assert board_tool_access.stripped(12) == ""
