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

"""Helpers for the board agent tests: skills, stage agents, a stubbed model and run jobs.

No model is ever called. :class:`Runner` stands in for ``run_agent_for_org_id``
and plays one scripted step per run: reply with text, call MCP tools through
the real ``/mcp/tools`` route with the run's own token, or fail. Jobs are
captured instead of queued (:class:`Jobs`) and run by the test, so each run's
steps happen in a known order.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.config import settings
from app.models.agent_skill import AgentSkill, AgentType
from app.models.board_agent import BoardCardAgentRun
from app.services.agents import executor
from app.services.boards.agents import queue
from app.services.boards.agents.run_handler import handle_board_agent_run_job
from app.services.claude_runner import ClaudeRunnerConfig, ClaudeRunResult
from tests.fakes.app_state import bind_app_sessions
from tests.integration.board_api_support import BOARDS, Person, ok
from tests.integration.board_notify_support import Slack, fake_slack
from tests.integration.mcp_support import drain_background
from tests.integration.scan_features_bugs_support import Factory

Step = Callable[[ClaudeRunnerConfig], Awaitable[ClaudeRunResult]]


async def add_skill(
    factory: Factory,
    org: uuid.UUID,
    *,
    agent_type: AgentType = AgentType.BOARD_PRD,
    mcp_tools: list[str] | None = None,
    name: str = "PRD writer",
) -> uuid.UUID:
    """A custom skill in ``org``'s library."""
    async with factory() as db:
        skill = AgentSkill(
            org_id=org,
            skill_slug=f"skill-{uuid.uuid4().hex[:8]}",
            agent_type=agent_type,
            name=name,
            prompt="Write the document the card needs.",
            mcp_tools=mcp_tools or [],
            is_custom=True,
        )
        db.add(skill)
        await db.commit()
        return skill.id


async def set_agents(
    client: AsyncClient, admin: Person, key: str, stage: str, agents: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Replace a stage's agents; the stored list."""
    url = f"{BOARDS}/{key}/stages/{stage}/agents"
    return list(ok(await client.put(url, json=agents, headers=admin.headers)))


def agent(
    skill: uuid.UUID, trigger: str = "on_enter", order: int = 1, **rest: Any
) -> dict[str, Any]:
    """One stage agent as the config API takes it."""
    return {"skill_id": str(skill), "trigger": trigger, "order": order, **rest}


async def ai_on(client: AsyncClient, admin: Person, key: str, enabled: bool = True) -> None:
    """Turn the board's AI switch on (or off)."""
    ok(await client.patch(f"{BOARDS}/{key}", json={"ai_enabled": enabled}, headers=admin.headers))


async def runs_of(factory: Factory, card_id: str) -> list[BoardCardAgentRun]:
    """Every run on a card, oldest first."""
    async with factory() as db:
        rows = await db.scalars(
            select(BoardCardAgentRun)
            .where(BoardCardAgentRun.card_id == uuid.UUID(card_id))
            .order_by(BoardCardAgentRun.created_at, BoardCardAgentRun.attempt)
        )
        return list(rows)


@dataclass
class Jobs:
    """Board agent jobs captured instead of queued, and the jobs canceled."""

    queued: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    canceled: list[tuple[str, str]] = field(default_factory=list)
    full: bool = False

    async def run_all(self) -> None:
        """Run every captured job, in order."""
        while self.queued:
            job_id, payload = self.queued.pop(0)
            await handle_board_agent_run_job(job_id, payload)


def capture_jobs(monkeypatch: pytest.MonkeyPatch) -> Jobs:
    """Capture ``board_agent_run`` jobs and cancels instead of touching the real queue."""
    jobs = Jobs()

    def _create(job_id: str, job_type: str, *, payload: dict[str, Any], **_: Any) -> None:
        if jobs.full:
            raise asyncio.QueueFull()
        jobs.queued.append((job_id, payload))

    def _cancel(job_id: str, *, reason: str) -> bool:
        jobs.canceled.append((job_id, reason))
        return True

    monkeypatch.setattr(queue, "create_job_with_id", _create)
    monkeypatch.setattr("app.services.boards.agents.runs.cancel_job", _cancel)
    return jobs


@dataclass
class Runner:
    """The stubbed model: one scripted step per run, and what each run was given."""

    client: AsyncClient
    steps: list[Step] = field(default_factory=list)
    prompts: list[str] = field(default_factory=list)
    configs: list[ClaudeRunnerConfig] = field(default_factory=list)

    async def __call__(
        self, org_id: uuid.UUID | None, prompt: str, working_dir: Any, config: Any = None, **_: Any
    ) -> ClaudeRunResult:
        self.prompts.append(prompt)
        self.configs.append(config)
        step = self.steps.pop(0)
        return await step(config)

    def reply(self, text: str) -> None:
        """The next run answers with ``text`` and calls no tool."""

        async def _step(_config: ClaudeRunnerConfig) -> ClaudeRunResult:
            return ClaudeRunResult(success=True, output=text)

        self.steps.append(_step)

    def fail(self, error: str = "credit balance too low") -> None:
        """The next run fails at the provider."""

        async def _step(_config: ClaudeRunnerConfig) -> ClaudeRunResult:
            return ClaudeRunResult(success=False, output="", error=error)

        self.steps.append(_step)

    def calls(
        self, *tool_calls: tuple[str, dict[str, Any]], seen: list[Any] | None = None
    ) -> None:
        """The next run calls each tool over ``/mcp/tools`` with its token, then replies "done"."""

        async def _step(config: ClaudeRunnerConfig) -> ClaudeRunResult:
            assert config.mcp is not None
            for tool, params in tool_calls:
                resp = await self.client.post(
                    f"/mcp/tools/{tool}",
                    json={"params": params},
                    headers={"Authorization": f"Bearer {config.mcp.mcp_token}"},
                )
                if seen is not None:
                    seen.append(resp)
            return ClaudeRunResult(success=True, output="done")

        self.steps.append(_step)


def stub_runner(monkeypatch: pytest.MonkeyPatch, client: AsyncClient) -> Runner:
    """Swap the provider call for a :class:`Runner`, with MCP tokens minted for it."""
    runner = Runner(client)
    monkeypatch.setattr(executor, "run_agent_for_org_id", runner)
    monkeypatch.setattr(settings, "mcp_backend_url", "http://test")
    return runner


@dataclass(frozen=True)
class AgentEnv:
    """The captured jobs, the stubbed model and the faked Slack for one test."""

    jobs: Jobs
    runner: Runner
    slack: Slack


@pytest_asyncio.fixture
async def agent_env(
    monkeypatch: pytest.MonkeyPatch,
    pg_session_factory: Factory,
    client: AsyncClient,
    mcp_env: None,
) -> AsyncIterator[AgentEnv]:
    """Background sessions on the test database, jobs captured, the model stubbed."""
    bind_app_sessions(monkeypatch, pg_session_factory)
    env = AgentEnv(
        jobs=capture_jobs(monkeypatch),
        runner=stub_runner(monkeypatch, client),
        slack=fake_slack(monkeypatch, pg_session_factory),
    )
    yield env
    await env.slack.flush()
    await drain_background()
