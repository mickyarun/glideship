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

"""A card run's MCP token: one card, its own tools, its own org, and only while it runs.

The stubbed model calls the real ``/mcp/tools`` and ``/mcp/sse`` routes with
the token, so the grant is checked as a CLI provider would hit it.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient

from app.mcp.auth import create_internal_mcp_token
from tests.integration.board_agent_setup import agent_card, docs, start
from tests.integration.board_agent_support import (
    AgentEnv,
    agent_env,
)
from tests.integration.board_api_support import (
    BOARDS,
    make_board,
    make_card,
    person,
)
from tests.integration.mcp_support import mcp_env
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration
__all__ = ["agent_env", "mcp_env"]


async def test_the_runs_token_is_scoped_to_its_card_tools_and_lifetime(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory)
    other = await make_card(client, s.admin, s.key, "Other")
    stranger_org = await new_org(pg_session_factory)
    stranger = await person(pg_session_factory, stranger_org, "org_owner")
    foreign_board = await make_board(client, stranger)
    foreign = await make_card(client, stranger, foreign_board["board"]["key"])
    seen: list[Any] = []
    write = {"kind": "prd", "content_md": "x"}
    agent_env.runner.calls(
        ("write_card_doc", {**write, "card_id": other["id"]}),
        ("write_card_doc", {**write, "card_key": other["key"]}),
        ("write_card_doc", {**write, "card_id": foreign["id"]}),
        ("get_bud_context", {}),
        ("write_bud", {"bud_id": str(uuid.uuid4()), "content": "x"}),
        seen=seen,
    )
    tokens: list[str] = []
    real = agent_env.runner.steps[0]

    async def keep_token(config: Any) -> Any:
        tokens.append(config.mcp.mcp_token)
        return await real(config)

    agent_env.runner.steps[0] = keep_token
    await start(client, s)
    await agent_env.jobs.run_all()
    assert [r.status_code for r in seen] == [403, 403, 403, 403, 403]
    # Only the reply landed, as a draft on the run's own card.
    (draft,) = (await docs(client, s))["drafts"]
    assert draft["body_md"] == "done"
    assert (
        await client.get(f"{BOARDS}/{s.key}/cards/{other['number']}/docs", headers=s.admin.headers)
    ).json()["drafts"] == []
    # The run is over: its token is gone.
    after = await client.post(
        "/mcp/tools/get_card_context",
        json={"params": {}},
        headers={"Authorization": f"Bearer {tokens[0]}"},
    )
    assert after.status_code == 401


async def test_an_org_wide_token_cannot_use_the_card_tools(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory)
    token = create_internal_mcp_token(s.org)
    resp = await client.post(
        "/mcp/tools/write_card_doc",
        json={"params": {"card_id": s.card["id"], "kind": "prd", "content_md": "x"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    remote = await client.post(
        "/mcp/sse",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "write_card_doc", "arguments": {}},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert "not available remotely" in remote.text
