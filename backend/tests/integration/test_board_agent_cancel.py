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

"""Canceling a card's agent run from its AI panel: editors only, pending or running only."""

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
from app.schemas.jobs import JobState
from app.services import event_bus
from app.services.boards.agents.cancel import CANCELED_BY_PERSON
from app.services.claude_runner import ClaudeRunnerConfig, ClaudeRunResult
from tests.integration.board_agent_setup import Setup, agent_card, start
from tests.integration.board_agent_support import AgentEnv, agent_env, runs_of
from tests.integration.board_api_support import make_card, ok, person, put_role
from tests.integration.mcp_support import mcp_env
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration
__all__ = ["agent_env", "mcp_env"]


def _cancel_url(s: Setup, run_id: str, number: int | None = None) -> str:
    base = s.card_url if number is None else s.card_url.rsplit("/", 1)[0] + f"/{number}"
    return f"{base}/agents/runs/{run_id}/cancel"


async def _ai_events(factory: Factory, card_id: str) -> list[BoardCardEvent]:
    async with factory() as db:
        rows = await db.scalars(
            select(BoardCardEvent).where(
                BoardCardEvent.card_id == uuid.UUID(card_id),
                BoardCardEvent.type == BoardCardEventType.AI_RUN,
            )
        )
        return list(rows)


async def test_an_editor_cancels_a_queued_run_and_its_job_never_starts(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory)
    started = await start(client, s)
    run_id = started["run"]["id"]
    queue = event_bus.subscribe(f"board:{s.board_id}")
    try:
        canceled = ok(await client.post(_cancel_url(s, run_id), headers=s.assignee.headers))
        await asyncio.sleep(0)
        live: list[dict[str, Any]] = [queue.get_nowait()["data"] for _ in range(queue.qsize())]
    finally:
        event_bus.unsubscribe(f"board:{s.board_id}", queue)

    assert (canceled["status"], canceled["error_code"]) == ("canceled", "CANCELED")
    # The editor isn't a board admin, so the raw reason isn't theirs to read.
    assert canceled["error_message"] is None
    (update,) = [e for e in live if e["event"] == "agent_run_updated"]
    assert (update["run"]["status"], update["skill_name"]) == ("canceled", "PRD writer")
    assert update["actor_id"] == str(s.assignee.id)
    (event,) = await _ai_events(pg_session_factory, s.card["id"])
    assert (event.actor_id, event.detail["status"]) == (s.assignee.id, "canceled")
    assert event.detail["error_code"] == "CANCELED"
    assert agent_env.jobs.canceled == [(started["job_id"], CANCELED_BY_PERSON)]
    # Its job finds the run canceled and never reaches the model.
    await agent_env.jobs.run_all()
    assert agent_env.jobs.state(started["job_id"]) is JobState.CANCELLED
    assert agent_env.runner.configs == []
    (run,) = await runs_of(pg_session_factory, s.card["id"])
    assert (run.status, run.error_code) == (
        BoardAgentRunStatus.CANCELED,
        BoardAgentRunErrorCode.CANCELED,
    )
    # A new run can start straight away.
    agent_env.runner.reply("Fresh")
    assert (await start(client, s))["run"]["attempt"] == 2


async def test_canceling_a_running_run_saves_nothing_and_ends_its_job_canceled(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory)
    started = await start(client, s)
    answers: list[int] = []

    async def _canceled_mid_run(_config: ClaudeRunnerConfig) -> ClaudeRunResult:
        resp = await client.post(_cancel_url(s, started["run"]["id"]), headers=s.admin.headers)
        answers.append(resp.status_code)
        return ClaudeRunResult(success=True, output="# A PRD nobody wants now")

    agent_env.runner.steps.append(_canceled_mid_run)
    await agent_env.jobs.run_all()

    assert answers == [200]
    assert agent_env.jobs.state(started["job_id"]) is JobState.CANCELLED
    (run,) = await runs_of(pg_session_factory, s.card["id"])
    assert run.status is BoardAgentRunStatus.CANCELED
    docs = ok(await client.get(f"{s.card_url}/docs", headers=s.admin.headers))
    assert docs == {"items": [], "drafts": []}


async def test_a_finished_run_is_409_and_the_admin_reads_the_reason(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory)
    run_id = (await start(client, s))["run"]["id"]
    ok(await client.post(_cancel_url(s, run_id), headers=s.admin.headers))

    again = await client.post(_cancel_url(s, run_id), headers=s.admin.headers)
    assert again.status_code == 409
    assert (again.json()["code"], again.json()["status"]) == ("AGENT_RUN_FINISHED", "canceled")
    (run,) = ok(await client.get(f"{s.card_url}/agents", headers=s.admin.headers))["runs"]
    assert run["error_message"] == CANCELED_BY_PERSON

    agent_env.runner.reply("# PRD")
    done = (await start(client, s))["run"]["id"]
    await agent_env.jobs.run_all()
    finished = await client.post(_cancel_url(s, done), headers=s.admin.headers)
    assert (finished.status_code, finished.json()["status"]) == (409, "completed")


async def test_viewers_cant_cancel_and_another_cards_run_is_not_found(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory)
    run_id = (await start(client, s))["run"]["id"]
    viewer = await person(pg_session_factory, s.org)
    await put_role(client, s.admin, s.key, viewer.id, "viewer")
    other = await make_card(client, s.admin, s.key, "Other")

    refused = await client.post(_cancel_url(s, run_id), headers=viewer.headers)
    assert refused.status_code == 403
    elsewhere = await client.post(_cancel_url(s, run_id, other["number"]), headers=s.admin.headers)
    assert elsewhere.status_code == 404
    unknown = await client.post(_cancel_url(s, str(uuid.uuid4())), headers=s.admin.headers)
    assert unknown.status_code == 404
    (run,) = await runs_of(pg_session_factory, s.card["id"])
    assert run.status is BoardAgentRunStatus.PENDING
