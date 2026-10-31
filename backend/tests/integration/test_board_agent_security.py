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

"""A card run's guard rails: no built-in tools, who it acts for, its token's routes and life."""

from __future__ import annotations

import dataclasses
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.mcp import token_grants
from app.models.board_agent import BoardAgentRunStatus, BoardCardAgentRun
from app.schemas.jobs import JobState
from app.services.boards.agents.card_tools import RUN_OVER
from app.services.boards.agents.output import TOO_LONG
from app.services.boards.constants import CARD_DOC_MAX_CHARS, CARD_RUN_TOOLS
from app.services.claude_runner import ClaudeRunnerConfig, ClaudeRunResult
from tests.integration.board_agent_setup import Setup, agent_card, docs, start
from tests.integration.board_agent_support import AgentEnv, agent_env, runs_of
from tests.integration.board_api_support import BOARDS, ok, person
from tests.integration.mcp_support import mcp_env
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration
__all__ = ["agent_env", "mcp_env"]

READS = ["get_features", "list_design_systems", "get_team_context", "write_bud"]


def _bearer(config: ClaudeRunnerConfig) -> dict[str, str]:
    assert config.mcp is not None
    return {"Authorization": f"Bearer {config.mcp.mcp_token}"}


async def test_a_card_run_gets_no_built_in_tools_and_only_allowlisted_reads(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory, mcp_tools=READS)
    agent_env.runner.reply("# PRD")
    await start(client, s)
    await agent_env.jobs.run_all()
    (config,) = agent_env.runner.configs
    assert config.builtin_tools == []
    assert config.mcp is not None and config.mcp.grant is not None
    assert set(config.mcp.tool_names) == CARD_RUN_TOOLS | {"get_features", "list_design_systems"}


async def test_a_run_started_without_engineering_access_gets_no_read_tools(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory, mcp_tools=READS)
    seller = await person(pg_session_factory, s.org, "sales")
    url = f"{BOARDS}/{s.key}/members/{seller.id}"
    ok(await client.put(url, json={"role": "editor"}, headers=s.admin.headers))
    agent_env.runner.reply("# PRD")
    run_url = f"{s.card_url}/agents/{s.agent_id}/run"
    ok(await client.post(run_url, headers=seller.headers), 202)
    await agent_env.jobs.run_all()
    (config,) = agent_env.runner.configs
    assert config.mcp is not None and set(config.mcp.tool_names) == CARD_RUN_TOOLS


async def test_the_runs_token_is_refused_on_hooks_other_tools_and_shows_only_its_own(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory)
    seen: dict[str, Any] = {}

    async def step(config: ClaudeRunnerConfig) -> ClaudeRunResult:
        auth = _bearer(config)
        for hook in ("dev-activity", "agent-activity"):
            seen[hook] = (await client.post(f"/mcp/{hook}", json={}, headers=auth)).status_code
        listed = (await client.get("/mcp/tools", headers=auth)).json()
        seen["listed"] = {t["name"] for t in listed}
        rpc = {"name": "get_features", "arguments": {}}
        body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": rpc}
        seen["sse"] = (await client.post("/mcp/sse", json=body, headers=auth)).text
        return ClaudeRunResult(success=True, output="done")

    agent_env.runner.steps.append(step)
    await start(client, s)
    await agent_env.jobs.run_all()
    assert seen["dev-activity"] == seen["agent-activity"] == 403
    assert seen["listed"] == CARD_RUN_TOOLS
    assert "not in this token's grant" in seen["sse"]


async def test_a_token_that_expires_mid_run_stops_working(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory)
    codes: list[int] = []

    async def step(config: ClaudeRunnerConfig) -> ClaudeRunResult:
        assert config.mcp is not None and config.mcp.grant is not None
        token, params = config.mcp.mcp_token, {"json": {"params": {}}, "headers": _bearer(config)}
        codes.append((await client.post("/mcp/tools/get_card_context", **params)).status_code)
        past = datetime.now(UTC) - timedelta(seconds=1)
        token_grants._scoped_tokens[token] = dataclasses.replace(config.mcp.grant, expires_at=past)
        codes.append((await client.post("/mcp/tools/get_card_context", **params)).status_code)
        return ClaudeRunResult(success=True, output="done")

    agent_env.runner.steps.append(step)
    await start(client, s)
    await agent_env.jobs.run_all()
    assert codes == [200, 401]


async def _cancel(factory: Factory, s: Setup) -> None:
    async with factory() as db:
        await db.execute(
            update(BoardCardAgentRun)
            .where(BoardCardAgentRun.card_id == uuid.UUID(s.card["id"]))
            .values(status=BoardAgentRunStatus.CANCELED)
        )
        await db.commit()


async def test_write_card_doc_after_the_run_was_canceled_is_refused(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory)
    seen: list[tuple[int, str]] = []

    async def step(config: ClaudeRunnerConfig) -> ClaudeRunResult:
        await _cancel(pg_session_factory, s)
        write = {"params": {"card_id": s.card["id"], "kind": "prd", "content_md": "# PRD"}}
        resp = await client.post("/mcp/tools/write_card_doc", json=write, headers=_bearer(config))
        seen.append((resp.status_code, resp.json()["detail"]))
        return ClaudeRunResult(success=True, output="late reply")

    agent_env.runner.steps.append(step)
    started = await start(client, s)
    await agent_env.jobs.run_all()
    assert seen == [(403, RUN_OVER)]
    assert agent_env.jobs.state(started["job_id"]) is JobState.CANCELLED
    assert (await docs(client, s))["drafts"] == []
    (run,) = await runs_of(pg_session_factory, s.card["id"])
    assert run.status is BoardAgentRunStatus.CANCELED


async def test_an_oversized_reply_fails_the_run_and_saves_nothing(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory)
    agent_env.runner.reply("x" * (CARD_DOC_MAX_CHARS + 1))
    await start(client, s)
    await agent_env.jobs.run_all()
    (run,) = await runs_of(pg_session_factory, s.card["id"])
    assert run.status is BoardAgentRunStatus.FAILED and run.error_message == TOO_LONG
    assert (await docs(client, s))["drafts"] == []
