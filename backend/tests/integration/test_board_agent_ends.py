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

"""How a card run ends when something stops it: the run row, the job's state and the Garden.

A run stopped by someone else ends its job ``cancelled`` (never done or
failed) and saves nothing; a run whose skill was deleted mid-run still frees
its card when it crashes; and the Garden always hears a started run end.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, update

from app.models.agent_skill import AgentSkill
from app.models.board import Board
from app.models.board_agent import BoardAgentRunErrorCode, BoardAgentRunStatus, BoardCardAgentRun
from app.schemas.jobs import JobState
from app.services import event_bus
from app.services.boards import card_move
from app.services.boards.agents import subject
from app.services.boards.agents.loading import AI_OFF
from app.services.claude_runner import ClaudeRunnerConfig, ClaudeRunResult
from tests.integration.board_agent_setup import Setup, agent_card, ai_board, docs, move, start
from tests.integration.board_agent_support import (
    AgentEnv,
    add_skill,
    agent,
    agent_env,
    runs_of,
    set_agents,
)
from tests.integration.board_api_support import make_card, ok, stage_id
from tests.integration.mcp_support import mcp_env
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration
__all__ = ["agent_env", "mcp_env"]


async def _set_run(factory: Factory, s: Setup, status: BoardAgentRunStatus) -> None:
    async with factory() as db:
        await db.execute(
            update(BoardCardAgentRun)
            .where(BoardCardAgentRun.card_id == uuid.UUID(s.card["id"]))
            .values(status=status, error_message="Stopped by a test.")
        )
        await db.commit()


async def test_a_rolled_back_move_starts_no_run(
    client: AsyncClient,
    pg_session_factory: Factory,
    agent_env: AgentEnv,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _org, admin, board, _skill = await ai_board(client, pg_session_factory)
    key = board["board"]["key"]
    card = await make_card(client, admin, key, "Moves", stage_id=stage_id(board, "To do"))

    async def broken(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("the move failed after its run was claimed")

    monkeypatch.setattr(card_move, "card_detail", broken)
    with pytest.raises(RuntimeError):
        await move(client, admin, key, card["number"], stage_id(board, "In progress"))
    assert await runs_of(pg_session_factory, card["id"]) == []
    assert agent_env.jobs.queued == []


async def test_ai_switched_off_before_the_job_starts_cancels_run_and_job(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory)
    started = await start(client, s)
    async with pg_session_factory() as db:
        await db.execute(
            update(Board).where(Board.id == uuid.UUID(s.board_id)).values(ai_enabled=False)
        )
        await db.commit()
    await agent_env.jobs.run_all()
    (run,) = await runs_of(pg_session_factory, s.card["id"])
    assert (run.status, run.error_message) == (BoardAgentRunStatus.CANCELED, AI_OFF)
    assert run.error_code is BoardAgentRunErrorCode.CANCELED
    assert agent_env.jobs.state(started["job_id"]) is JobState.CANCELLED
    assert agent_env.runner.configs == []


async def test_a_run_stopped_before_it_starts_never_reaches_the_model(
    client: AsyncClient,
    pg_session_factory: Factory,
    agent_env: AgentEnv,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = await agent_card(client, pg_session_factory)
    real = subject.card_context

    async def stopped_meanwhile(*args: Any) -> Any:
        await _set_run(pg_session_factory, s, BoardAgentRunStatus.CANCELED)
        return await real(*args)

    monkeypatch.setattr(subject, "card_context", stopped_meanwhile)
    started = await start(client, s)
    await agent_env.jobs.run_all()
    (run,) = await runs_of(pg_session_factory, s.card["id"])
    assert (run.status, run.started_at) == (BoardAgentRunStatus.CANCELED, None)
    assert agent_env.jobs.state(started["job_id"]) is JobState.CANCELLED
    assert agent_env.runner.configs == []


async def test_a_cancel_while_the_model_answers_saves_nothing_and_cancels_the_job(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory)

    async def step(_config: ClaudeRunnerConfig) -> ClaudeRunResult:
        await _set_run(pg_session_factory, s, BoardAgentRunStatus.CANCELED)
        return ClaudeRunResult(success=True, output="# Late PRD")

    agent_env.runner.steps.append(step)
    started = await start(client, s)
    await agent_env.jobs.run_all()
    assert (await docs(client, s))["drafts"] == []
    assert agent_env.jobs.state(started["job_id"]) is JobState.CANCELLED
    (run,) = await runs_of(pg_session_factory, s.card["id"])
    assert run.status is BoardAgentRunStatus.CANCELED


async def test_a_crash_after_the_skill_was_deleted_still_frees_the_card(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory)

    async def step(_config: ClaudeRunnerConfig) -> ClaudeRunResult:
        async with pg_session_factory() as db:
            await db.execute(delete(AgentSkill).where(AgentSkill.org_id == s.org))
            await db.commit()
        raise RuntimeError("provider blew up")

    agent_env.runner.steps.append(step)
    started = await start(client, s)
    await agent_env.jobs.run_all()
    (run,) = await runs_of(pg_session_factory, s.card["id"])
    assert (run.status, run.skill_id) == (BoardAgentRunStatus.FAILED, None)
    assert agent_env.jobs.state(started["job_id"]) is JobState.FAILED
    skill = await add_skill(pg_session_factory, s.org)
    stage = s.card["stage_id"]
    (fresh,) = await set_agents(client, s.admin, s.key, stage, [agent(skill, "manual")])
    url = f"{s.card_url}/agents/{fresh['id']}/run"
    ok(await client.post(url, headers=s.admin.headers), 202)


async def test_a_canceled_run_tells_the_garden_it_ended(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory)

    async def cancel(_config: Any) -> Any:
        raise asyncio.CancelledError

    agent_env.runner.steps.append(cancel)
    garden = event_bus.subscribe(f"agent_activity:{s.org}")
    try:
        await start(client, s)
        with pytest.raises(asyncio.CancelledError):
            await agent_env.jobs.run_all()
        activity = [garden.get_nowait()["data"] for _ in range(garden.qsize())]
    finally:
        event_bus.unsubscribe(f"agent_activity:{s.org}", garden)
    assert [(e["event_type"], e["status"]) for e in activity] == [
        ("skill_invoked", "in_progress"),
        ("skill_failed", "failed"),
    ]
    (run,) = await runs_of(pg_session_factory, s.card["id"])
    assert run.status is BoardAgentRunStatus.CANCELED
