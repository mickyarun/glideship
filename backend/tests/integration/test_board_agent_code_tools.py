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

"""A card run's code tools read only the board's active linked repositories."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.models.tracked_repository import RepoStatus, TrackedRepository
from app.services.claude_runner import ClaudeRunnerConfig, ClaudeRunResult
from tests.integration.board_agent_setup import Setup, agent_card, start
from tests.integration.board_agent_support import AgentEnv, agent_env
from tests.integration.board_api_support import link_repo, tracked_repo
from tests.integration.mcp_support import mcp_env
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration
__all__ = ["agent_env", "mcp_env"]

CODE = ["code_query", "code_context", "get_features"]


async def _retire(factory: Factory, repo: uuid.UUID) -> None:
    async with factory() as db:
        await db.execute(
            update(TrackedRepository)
            .where(TrackedRepository.id == repo)
            .values(status=RepoStatus.REMOVED)
        )
        await db.commit()


async def _probe(
    client: AsyncClient, agent_env: AgentEnv, repos: list[uuid.UUID]
) -> dict[str, Any]:
    seen: dict[str, Any] = {"codes": []}

    async def step(config: ClaudeRunnerConfig) -> ClaudeRunResult:
        assert config.mcp is not None
        auth = {"Authorization": f"Bearer {config.mcp.mcp_token}"}
        for repo in repos:
            body = {"params": {"query": "refund", "repo_id": str(repo)}}
            resp = await client.post("/mcp/tools/code_query", json=body, headers=auth)
            seen["codes"].append(resp.status_code)
        listed = (await client.get("/mcp/tools", headers=auth)).json()
        seen["schema"] = next(t for t in listed if t["name"] == "code_query")["input_schema"]
        return ClaudeRunResult(success=True, output="done")

    agent_env.runner.steps.append(step)
    return seen


async def _linked(client: AsyncClient, factory: Factory, s: Setup) -> dict[str, uuid.UUID]:
    mine = await tracked_repo(factory, s.org)
    retired = await tracked_repo(factory, s.org)
    await link_repo(client, s.admin, s.key, mine)
    await link_repo(client, s.admin, s.key, retired)
    await _retire(factory, retired)
    unlinked = await tracked_repo(factory, s.org)
    foreign = await tracked_repo(factory, await new_org(factory))
    return {"mine": mine, "retired": retired, "unlinked": unlinked, "foreign": foreign}


async def test_code_tools_reach_only_the_boards_active_linked_repos(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory, mcp_tools=CODE)
    repos = await _linked(client, pg_session_factory, s)
    order = ["mine", "retired", "unlinked", "foreign"]
    seen = await _probe(client, agent_env, [repos[k] for k in order])
    await start(client, s)
    await agent_env.jobs.run_all()
    assert seen["codes"] == [200, 403, 403, 403]
    assert seen["schema"]["properties"]["repo_id"]["enum"] == [str(repos["mine"])]
    (config,) = agent_env.runner.configs
    assert config.mcp is not None and "code_query" in config.mcp.tool_names
    (prompt,) = agent_env.runner.prompts
    assert str(repos["mine"]) in prompt
    assert not any(str(repos[k]) in prompt for k in order[1:])


async def test_a_board_without_linked_repos_gets_no_code_tools(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory, mcp_tools=CODE)
    agent_env.runner.reply("# PRD")
    await start(client, s)
    await agent_env.jobs.run_all()
    (config,) = agent_env.runner.configs
    assert config.mcp is not None
    assert not {"code_query", "code_context"} & set(config.mcp.tool_names)
    assert "get_features" in config.mcp.tool_names
    assert "repo_id" not in agent_env.runner.prompts[0]
