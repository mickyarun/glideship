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

"""A card run end to end, with the model stubbed: prompt, token, draft, events, notices.

The stub calls ``write_card_doc`` through the real ``/mcp/tools`` route with
the run's own token, so the grant is checked as a CLI provider would hit it.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.agent_skill import AgentType
from app.models.board_agent import BoardAgentRunStatus
from app.models.board_card_detail import BoardCardEvent
from app.models.board_enums import BoardCardEventType
from app.models.notification import NotificationType
from app.services import event_bus
from tests.integration.board_agent_setup import Setup, agent_card, docs, start
from tests.integration.board_agent_support import (
    AgentEnv,
    agent_env,
    runs_of,
)
from tests.integration.board_api_support import (
    link_repo,
    ok,
    tracked_repo,
)
from tests.integration.board_notify_support import notes
from tests.integration.mcp_support import mcp_env
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration
__all__ = ["agent_env", "mcp_env"]


async def _ai_notes(factory: Factory, s: Setup) -> list[NotificationType]:
    ai = {NotificationType.BOARD_AI_DRAFT, NotificationType.BOARD_AI_FAILED}
    return [n.type for n in await notes(factory, s.assignee.id) if n.type in ai]


async def _ai_events(factory: Factory, card_id: str) -> list[BoardCardEvent]:
    async with factory() as db:
        rows = await db.scalars(
            select(BoardCardEvent).where(
                BoardCardEvent.card_id == uuid.UUID(card_id),
                BoardCardEvent.type == BoardCardEventType.AI_RUN,
            )
        )
        return list(rows)


async def test_the_tool_writes_a_draft_and_the_run_completes(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory)
    seen: list[Any] = []
    agent_env.runner.calls(
        ("get_card_context", {"card_id": s.card["id"]}),
        ("write_card_doc", {"card_key": s.card["key"], "kind": "prd", "content_md": "# PRD"}),
        seen=seen,
    )
    queue = event_bus.subscribe(f"board:{s.board_id}")
    garden = event_bus.subscribe(f"agent_activity:{s.org}")
    try:
        await start(client, s)
        await agent_env.jobs.run_all()
        await asyncio.sleep(0)
        events = [queue.get_nowait()["data"] for _ in range(queue.qsize())]
        activity = [garden.get_nowait()["data"]["event_type"] for _ in range(garden.qsize())]
    finally:
        event_bus.unsubscribe(f"board:{s.board_id}", queue)
        event_bus.unsubscribe(f"agent_activity:{s.org}", garden)
    context, written = (r.json() for r in seen)
    assert context["card"]["title"] == "Refunds page"
    assert written["state"] == "pending_review"
    (run,) = await runs_of(pg_session_factory, s.card["id"])
    assert run.status is BoardAgentRunStatus.COMPLETED
    assert run.result_summary == {"kind": "prd", "version": 1, "via": "tool"}
    listed = await docs(client, s)
    assert listed["items"] == []
    (draft,) = listed["drafts"]
    assert (draft["state"], draft["body_md"], draft["agent_run_id"]) == (
        "pending_review",
        "# PRD",
        str(run.id),
    )
    card = ok(await client.get(s.card_url, headers=s.admin.headers))
    assert card["has_prd"] is False
    (event,) = await _ai_events(pg_session_factory, s.card["id"])
    assert event.actor_id is None and event.detail["status"] == "completed"
    names = [e["event"] for e in events]
    assert "doc_updated" in names
    statuses = [e["run"]["status"] for e in events if e["event"] == "agent_run_updated"]
    assert statuses == ["pending", "running", "completed"]
    assert activity == ["skill_invoked", "skill_completed"]
    assert await _ai_notes(pg_session_factory, s) == [NotificationType.BOARD_AI_DRAFT]


async def test_without_the_tool_the_reply_is_saved_as_the_skills_kind(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory, agent_type=AgentType.BOARD_DESIGN)
    agent_env.runner.reply("## Screens\n- Refund form")
    await start(client, s)
    await agent_env.jobs.run_all()
    (draft,) = (await docs(client, s))["drafts"]
    assert (draft["kind"], draft["body_md"], draft["source"]) == (
        "design_brief",
        "## Screens\n- Refund form",
        "agent",
    )
    (run,) = await runs_of(pg_session_factory, s.card["id"])
    assert run.result_summary and run.result_summary["via"] == "reply"


async def test_a_failed_run_leaves_the_card_notifies_and_can_be_retried(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory)
    agent_env.runner.fail("credit balance too low")
    await start(client, s)
    await agent_env.jobs.run_all()
    (run,) = await runs_of(pg_session_factory, s.card["id"])
    assert (run.status, run.error_message) == (
        BoardAgentRunStatus.FAILED,
        "credit balance too low",
    )
    assert await docs(client, s) == {"items": [], "drafts": []}
    assert await _ai_notes(pg_session_factory, s) == [NotificationType.BOARD_AI_FAILED]
    (event,) = await _ai_events(pg_session_factory, s.card["id"])
    assert event.detail["status"] == "failed"
    agent_env.runner.reply("Second try")
    retry = await start(client, s)
    assert retry["run"]["attempt"] == 2
    await agent_env.jobs.run_all()
    assert [r.status for r in await runs_of(pg_session_factory, s.card["id"])] == [
        BoardAgentRunStatus.FAILED,
        BoardAgentRunStatus.COMPLETED,
    ]


async def test_an_empty_reply_without_a_draft_fails(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory)
    agent_env.runner.reply("   ")
    await start(client, s)
    await agent_env.jobs.run_all()
    (run,) = await runs_of(pg_session_factory, s.card["id"])
    assert run.status is BoardAgentRunStatus.FAILED
    assert "without writing a draft" in (run.error_message or "")


async def test_the_prompt_lists_linked_repos_and_the_grant_only_safe_tools(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(
        client, pg_session_factory, mcp_tools=["get_features", "write_bud", "update_bud"]
    )
    repo = await tracked_repo(pg_session_factory, s.org, full_name="acme/refunds")
    await link_repo(client, s.admin, s.key, repo)
    agent_env.runner.reply("# PRD")
    await start(client, s)
    await agent_env.jobs.run_all()
    (prompt,) = agent_env.runner.prompts
    (config,) = agent_env.runner.configs
    assert "acme/refunds" in prompt and s.card["key"] in prompt
    assert s.card["id"] in prompt
    assert config.mcp is not None
    assert config.mcp.tool_names == ["get_card_context", "get_features", "write_card_doc"]


async def test_a_canceled_job_marks_the_run_canceled(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory)

    async def cancel(_config: Any) -> Any:
        raise asyncio.CancelledError

    agent_env.runner.steps.append(cancel)
    await start(client, s)
    with pytest.raises(asyncio.CancelledError):
        await agent_env.jobs.run_all()
    (run,) = await runs_of(pg_session_factory, s.card["id"])
    assert run.status is BoardAgentRunStatus.CANCELED
