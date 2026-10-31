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

"""What the board shows around a run: the tile's chip, stable agent ids, and failures it hears.

A card's summary carries its active run (``agent_run``) from the same page
query; an admin re-saving a stage keeps the ids of the agents it names; a
run the queue can't take fails like any other (history, event, notice); and
a draft on an archived card can't be reviewed.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from httpx import AsyncClient

from app.models.board_agent import BoardAgentRunStatus
from app.models.notification import NotificationType
from app.services import event_bus
from app.services.boards.agents import queue as agent_queue
from app.services.boards.agents.queue import QUEUE_FULL
from tests.integration.board_agent_setup import agent_card, ai_board, docs, move, start
from tests.integration.board_agent_support import (
    AgentEnv,
    add_skill,
    agent,
    agent_env,
    runs_of,
    set_agents,
)
from tests.integration.board_api_support import BOARDS, make_card, ok, page, person, stage_id
from tests.integration.board_notify_support import notes
from tests.integration.mcp_support import mcp_env
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration
__all__ = ["agent_env", "mcp_env"]


async def _tile(client: AsyncClient, s: Any) -> dict[str, Any]:
    body = await page(client, s.admin, s.key, s.card["stage_id"])
    return next(c for c in body["items"] if c["id"] == s.card["id"])


async def test_the_tile_shows_the_active_run_until_it_ends(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory)
    assert (await _tile(client, s))["agent_run"] is None
    await start(client, s)
    assert (await _tile(client, s))["agent_run"] == {
        "status": "pending",
        "skill_name": "PRD writer",
    }
    card = ok(await client.get(s.card_url, headers=s.admin.headers))
    assert card["agent_run"]["status"] == "pending"
    agent_env.runner.reply("# PRD")
    await agent_env.jobs.run_all()
    assert (await _tile(client, s))["agent_run"] is None


async def test_a_move_that_starts_a_run_carries_it_on_the_card(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    _org, admin, board, _skill = await ai_board(client, pg_session_factory)
    key = board["board"]["key"]
    card = await make_card(client, admin, key, "Moves", stage_id=stage_id(board, "To do"))
    moved = ok(await move(client, admin, key, card["number"], stage_id(board, "In progress")))
    assert moved["agent_run"] == {"status": "pending", "skill_name": "PRD writer"}


async def test_resaving_a_stage_keeps_the_agents_it_names(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory)
    agent_env.runner.reply("# PRD")
    await start(client, s)
    await agent_env.jobs.run_all()
    url = f"{BOARDS}/{s.key}/stages/{s.card['stage_id']}/agents"
    (stored,) = ok(await client.get(url, headers=s.admin.headers))
    other = await add_skill(pg_session_factory, s.org, name="Notes taker")
    body = [
        agent(other, "manual", order=1),
        {**agent(stored["skill_id"], "manual", order=2), "id": s.agent_id},
    ]
    added, kept = await set_agents(client, s.admin, s.key, s.card["stage_id"], body)
    assert kept["id"] == s.agent_id and added["id"] != s.agent_id
    assert (kept["order"], added["order"]) == (2, 1)
    agent_env.runner.reply("# PRD again")
    retry = await start(client, s)
    assert retry["run"]["attempt"] == 2
    await agent_env.jobs.run_all()
    ok(await client.put(url, json=[agent(other, "manual")], headers=s.admin.headers))
    stray = [{**agent(other, "manual"), "id": s.agent_id}]
    refused = await client.put(url, json=stray, headers=s.admin.headers)
    assert refused.status_code == 422


async def test_an_entry_the_queue_cannot_take_fails_like_any_run(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    org, admin, board, _skill = await ai_board(client, pg_session_factory)
    key = board["board"]["key"]
    assignee = await person(pg_session_factory, org)
    url = f"{BOARDS}/{key}/members/{assignee.id}"
    ok(await client.put(url, json={"role": "editor"}, headers=admin.headers))
    card = await make_card(
        client,
        admin,
        key,
        "Moves",
        stage_id=stage_id(board, "To do"),
        assignee_ids=[str(assignee.id)],
    )
    agent_env.jobs.full = True
    queue = event_bus.subscribe(f"board:{board['board']['id']}")
    try:
        ok(await move(client, admin, key, card["number"], stage_id(board, "In progress")))
        await asyncio.gather(*agent_queue._pending)
        await asyncio.sleep(0)
        events = [queue.get_nowait()["data"] for _ in range(queue.qsize())]
    finally:
        event_bus.unsubscribe(f"board:{board['board']['id']}", queue)
    (run,) = await runs_of(pg_session_factory, card["id"])
    assert (run.status, run.error_message) == (BoardAgentRunStatus.FAILED, QUEUE_FULL)
    statuses = [e["run"]["status"] for e in events if e["event"] == "agent_run_updated"]
    assert statuses[-1] == "failed"
    kinds = [n.type for n in await notes(pg_session_factory, assignee.id)]
    assert NotificationType.BOARD_AI_FAILED in kinds


async def test_drafts_on_an_archived_card_cannot_be_reviewed(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory)
    agent_env.runner.reply("# PRD")
    await start(client, s)
    await agent_env.jobs.run_all()
    (draft,) = (await docs(client, s))["drafts"]
    ok(await client.post(f"{s.card_url}/archive", headers=s.admin.headers))
    base = f"{s.card_url}/docs/{draft['kind']}/drafts/{draft['id']}"
    accept = await client.post(
        f"{base}/accept", json={"base_version": None}, headers=s.admin.headers
    )
    reject = await client.post(f"{base}/reject", headers=s.admin.headers)
    assert (accept.status_code, reject.status_code) == (409, 409)
