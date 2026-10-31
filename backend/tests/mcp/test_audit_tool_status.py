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

"""What an MCP audit row keeps of a board call: its named keys, and a refusal's status."""

import pytest

from app.mcp.audit import _sanitise_params, tool_result_status


def test_board_call_keys_are_kept_and_document_text_is_not() -> None:
    params = {
        "board_key": "OPS",
        "card_key": "OPS-1",
        "stage": "Done",
        "kind": "prd",
        "content_md": "# private",
        "body": "a comment",
    }
    assert _sanitise_params(params) == {
        "board_key": "OPS",
        "card_key": "OPS-1",
        "stage": "Done",
        "kind": "prd",
    }


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        ({"success": False, "status": 404, "error": "Card not found."}, 404),
        ({"success": False, "status": 409}, 409),
        ({"success": False, "status": 503}, 503),
        ({"success": True, "card": {}}, 200),
        ({"success": False, "error": "kind must be one of"}, 200),
        ({"success": False, "status": 302}, 200),
        ({"success": False, "status": True}, 200),
        ({"success": False, "status": "404"}, 200),
        ({"error": "not found", "status": 404}, 200),
        ([1, 2], 200),
        (None, 200),
    ],
)
def test_a_refused_tool_result_is_audited_with_its_own_status(
    result: object, expected: int
) -> None:
    assert tool_result_status(result) == expected
