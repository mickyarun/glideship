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

"""Why a card run ended, as a code: always in the API and live events, with the raw
message only for board admins."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import delete

from app.models.agent_skill import AgentSkill
from app.models.board_agent import BoardAgentRunErrorCode
from app.services import event_bus
from app.services.boards.agents import end_codes
from app.services.claude_errors import ClaudeErrorCode
from tests.integration.board_agent_setup import agent_card, start
from tests.integration.board_agent_support import AgentEnv, agent_env, runs_of
from tests.integration.board_api_support import ok
from tests.integration.mcp_support import mcp_env
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration
__all__ = ["agent_env", "mcp_env"]


@pytest.mark.parametrize(
    ("error", "provider_code", "expected"),
    [
        ("Claude CLI is not installed", ClaudeErrorCode.BINARY_MISSING, "AI_NOT_CONFIGURED"),
        ("Switch the organisation", ClaudeErrorCode.UNSUPPORTED, "AI_NOT_CONFIGURED"),
        ("timed out after 600 seconds", ClaudeErrorCode.TIMEOUT, "TIMEOUT"),
        ("reached its maximum turns", ClaudeErrorCode.MAX_TURNS, "PROVIDER_FAILED"),
        ("credit balance too low", None, "PROVIDER_FAILED"),
    ],
)
async def test_a_provider_failure_has_a_code_and_only_admins_read_its_message(
    client: AsyncClient,
    pg_session_factory: Factory,
    agent_env: AgentEnv,
    error: str,
    provider_code: ClaudeErrorCode | None,
    expected: str,
) -> None:
    s = await agent_card(client, pg_session_factory)
    agent_env.runner.fail(error, provider_code)
    await start(client, s)
    queue = event_bus.subscribe(f"board:{s.board_id}")
    try:
        await agent_env.jobs.run_all()
        await asyncio.sleep(0)
        live = [queue.get_nowait()["data"] for _ in range(queue.qsize())]
    finally:
        event_bus.unsubscribe(f"board:{s.board_id}", queue)

    (run,) = await runs_of(pg_session_factory, s.card["id"])
    assert run.error_code is BoardAgentRunErrorCode(expected)
    url = f"{s.card_url}/agents"
    (as_admin,) = ok(await client.get(url, headers=s.admin.headers))["runs"]
    (as_editor,) = ok(await client.get(url, headers=s.assignee.headers))["runs"]
    assert (as_admin["error_code"], as_admin["error_message"]) == (expected, error)
    assert (as_editor["error_code"], as_editor["error_message"]) == (expected, None)
    updates = [e for e in live if e["event"] == "agent_run_updated"]
    assert [u["run"]["status"] for u in updates] == ["running", "failed"]
    assert {u["skill_name"] for u in updates} == {"PRD writer"}
    assert updates[-1]["run"]["error_code"] == expected
    assert all(u["run"]["error_message"] is None for u in updates)


async def test_a_skill_deleted_before_the_run_starts_is_skill_gone(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory)
    started = await start(client, s)
    queue = event_bus.subscribe(f"board:{s.board_id}")
    try:
        async with pg_session_factory() as db:
            await db.execute(delete(AgentSkill).where(AgentSkill.org_id == s.org))
            await db.commit()
        await agent_env.jobs.run_all()
        await asyncio.sleep(0)
        live: list[dict[str, Any]] = [queue.get_nowait()["data"] for _ in range(queue.qsize())]
    finally:
        event_bus.unsubscribe(f"board:{s.board_id}", queue)

    (run,) = await runs_of(pg_session_factory, s.card["id"])
    assert run.error_code is BoardAgentRunErrorCode.SKILL_GONE
    assert run.id == uuid.UUID(started["run"]["id"])
    (update,) = [e for e in live if e["event"] == "agent_run_updated"]
    assert update["skill_name"] is None


async def test_the_queue_being_full_is_queue_full(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory)
    agent_env.jobs.full = True
    resp = await client.post(f"{s.card_url}/agents/{s.agent_id}/run", headers=s.admin.headers)
    assert resp.status_code == 503
    (run,) = await runs_of(pg_session_factory, s.card["id"])
    assert run.error_code is BoardAgentRunErrorCode.QUEUE_FULL


def test_a_cancel_while_the_server_shuts_down_is_interrupted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert end_codes.cancel() is BoardAgentRunErrorCode.CANCELED
    monkeypatch.setattr(end_codes, "is_shutting_down", lambda: True)
    assert end_codes.cancel() is BoardAgentRunErrorCode.INTERRUPTED


def test_an_unknown_provider_code_is_a_provider_failure() -> None:
    assert end_codes.provider_failure("something_new") is BoardAgentRunErrorCode.PROVIDER_FAILED
    assert end_codes.crash(RuntimeError("boom")) is BoardAgentRunErrorCode.UNKNOWN
