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

"""Switching a board's AI off stops the runs going on its cards."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.board_agent import BoardAgentRunErrorCode, BoardAgentRunStatus
from app.models.board_card_detail import BoardCardEvent
from app.models.board_enums import BoardCardEventType
from app.services import event_bus
from app.services.boards.agents.switch_off import AI_SWITCHED_OFF
from app.services.claude_runner import ClaudeRunnerConfig, ClaudeRunResult
from tests.integration.board_agent_setup import agent_card, docs, start
from tests.integration.board_agent_support import AgentEnv, agent_env, ai_on, runs_of
from tests.integration.mcp_support import mcp_env
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration
__all__ = ["agent_env", "mcp_env"]


async def _ai_events(factory: Factory, card_id: str) -> list[dict[str, Any]]:
    async with factory() as db:
        rows = await db.scalars(
            select(BoardCardEvent).where(
                BoardCardEvent.card_id == uuid.UUID(card_id),
                BoardCardEvent.type == BoardCardEventType.AI_RUN,
            )
        )
        return [r.detail for r in rows]


async def test_switching_ai_off_cancels_a_queued_run(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory)
    started = await start(client, s)
    queue = event_bus.subscribe(f"board:{s.board_id}")
    try:
        await ai_on(client, s.admin, s.key, enabled=False)
        await asyncio.sleep(0)
        events = [queue.get_nowait()["data"] for _ in range(queue.qsize())]
    finally:
        event_bus.unsubscribe(f"board:{s.board_id}", queue)
    (run,) = await runs_of(pg_session_factory, s.card["id"])
    assert run.status is BoardAgentRunStatus.CANCELED and run.error_message == AI_SWITCHED_OFF
    assert run.error_code is BoardAgentRunErrorCode.CANCELED
    assert agent_env.jobs.canceled == [(started["job_id"], AI_SWITCHED_OFF)]
    updates = [e for e in events if e["event"] == "agent_run_updated"]
    assert updates[-1]["run"]["status"] == "canceled"
    (event,) = await _ai_events(pg_session_factory, s.card["id"])
    assert event["status"] == "canceled"
    # The job, had it started, finds the run settled and runs nothing.
    await agent_env.jobs.run_all()
    assert agent_env.runner.configs == []


async def test_switching_ai_off_mid_run_keeps_its_output_out(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory)

    async def step(_config: ClaudeRunnerConfig) -> ClaudeRunResult:
        await ai_on(client, s.admin, s.key, enabled=False)
        return ClaudeRunResult(success=True, output="# Late PRD")

    agent_env.runner.steps.append(step)
    await start(client, s)
    await agent_env.jobs.run_all()
    (run,) = await runs_of(pg_session_factory, s.card["id"])
    assert run.status is BoardAgentRunStatus.CANCELED
    assert (await docs(client, s))["drafts"] == []
    assert len(await _ai_events(pg_session_factory, s.card["id"])) == 1


async def test_switching_ai_on_again_cancels_nothing(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory)
    await start(client, s)
    await ai_on(client, s.admin, s.key, enabled=True)
    (run,) = await runs_of(pg_session_factory, s.card["id"])
    assert run.status is BoardAgentRunStatus.PENDING and agent_env.jobs.canceled == []
