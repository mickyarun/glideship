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

"""Board MCP calls in ``mcp_audit_log``: the board, card, stage and kind they named, and a
refused call's own status rather than the 200 it answered with."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.integration.board_mcp_support import board_desk, remote_result, tool
from tests.integration.mcp_support import (
    Factory,
    audit_rows,
    mcp_env,  # noqa: F401
    rpc,
)

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("mcp_env")]


async def test_board_calls_record_what_they_named_and_refusals_their_status(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    d = await board_desk(client, pg_session_factory)
    key = d.card["key"]

    moved = await tool(client, d.pm, "move_card", card_key=key, stage="Waiting")
    assert moved["success"] is True
    refused = await tool(client, d.outsider, "get_card", card_key=key)
    assert (refused["success"], refused["status"]) == (False, 404)
    written = await tool(
        client, d.pm, "write_card_doc", card_key=key, kind="notes", content_md="secret text"
    )
    assert written["saved"] is True
    missing = await tool(client, d.pm, "get_board", board_key="NOPE")
    assert missing["status"] == 404

    rows = await audit_rows(pg_session_factory, d.org)
    seen = [(r.tool_name, r.status_code, r.params) for r in rows]
    assert seen == [
        ("move_card", 200, {"card_key": key, "stage": "Waiting"}),
        ("get_card", 404, {"card_key": key}),
        ("write_card_doc", 200, {"card_key": key, "kind": "notes"}),
        ("get_board", 404, {"board_key": "NOPE"}),
    ]


async def test_a_refused_remote_board_read_is_audited_with_its_status(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    d = await board_desk(client, pg_session_factory)

    is_error, out = remote_result(
        await rpc(client, d.outsider.token, "get_board", {"board_key": d.key})
    )
    assert is_error is True and out["status"] == 404
    _, fine = remote_result(await rpc(client, d.pm.token, "get_board", {"board_key": d.key}))
    assert fine["board"]["key"] == d.key

    rows = await audit_rows(pg_session_factory, d.org)
    assert [(r.tool_name, r.transport, r.status_code) for r in rows] == [
        ("get_board", "sse", 404),
        ("get_board", "sse", 200),
    ]
