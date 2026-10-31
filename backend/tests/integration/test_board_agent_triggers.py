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

"""When stage agents start: entering a stage, the Run button, and what stops them.

``on_enter`` starts on a move, a create and a move between boards; never on a
restore, a stage delete, a handover or a BUD sent back. Both need the board's
AI switch, and a card holds one active run.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.models.board_agent import BoardAgentRunStatus, BoardAgentTrigger
from tests.integration.board_agent_setup import ai_board, move
from tests.integration.board_agent_support import (
    AgentEnv,
    add_skill,
    agent,
    agent_env,
    ai_on,
    runs_of,
    set_agents,
)
from tests.integration.board_api_support import (
    BOARDS,
    make_board,
    make_card,
    ok,
    stage_id,
)
from tests.integration.board_handover_return_support import bud_of, handed, send_back
from tests.integration.board_handover_support import card, desk
from tests.integration.mcp_support import mcp_env
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration
__all__ = ["agent_env", "mcp_env"]


async def test_creating_a_card_in_an_on_enter_stage_starts_its_agent(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    _, admin, board, skill = await ai_board(client, pg_session_factory)
    key = board["board"]["key"]
    made = await make_card(client, admin, key, stage_id=stage_id(board, "In progress"))
    (run,) = await runs_of(pg_session_factory, made["id"])
    assert (run.trigger, run.status, run.skill_id) == (
        BoardAgentTrigger.ON_ENTER,
        BoardAgentRunStatus.PENDING,
        skill,
    )
    # The person whose create started it: their access decides the run's read tools.
    assert run.triggered_by == admin.id
    assert [job_id for job_id, _ in agent_env.jobs.queued] == [run.job_id]


async def test_moving_into_the_stage_starts_it_but_reordering_inside_does_not(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    _, admin, board, _ = await ai_board(client, pg_session_factory)
    key, target = board["board"]["key"], stage_id(board, "In progress")
    made = await make_card(client, admin, key)
    assert await runs_of(pg_session_factory, made["id"]) == []
    ok(await move(client, admin, key, made["number"], target))
    (run,) = await runs_of(pg_session_factory, made["id"])
    assert run.stage_id == uuid.UUID(target)
    agent_env.jobs.queued.clear()
    # Staying in the stage isn't an entry; the active run also blocks a second one.
    ok(await move(client, admin, key, made["number"], target))
    assert len(await runs_of(pg_session_factory, made["id"])) == 1
    assert agent_env.jobs.queued == []


async def test_a_move_while_a_run_is_going_goes_ahead_without_a_second_run(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    _, admin, board, skill = await ai_board(client, pg_session_factory)
    key = board["board"]["key"]
    await set_agents(client, admin, key, stage_id(board, "Waiting"), [agent(skill)])
    made = await make_card(client, admin, key, stage_id=stage_id(board, "In progress"))
    ok(await move(client, admin, key, made["number"], stage_id(board, "Waiting")))
    runs = await runs_of(pg_session_factory, made["id"])
    assert [r.stage_id for r in runs] == [uuid.UUID(stage_id(board, "In progress"))]


async def test_ai_switched_off_starts_nothing(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    _, admin, board, _ = await ai_board(client, pg_session_factory, ai=False)
    key = board["board"]["key"]
    made = await make_card(client, admin, key, stage_id=stage_id(board, "In progress"))
    made2 = await make_card(client, admin, key)
    ok(await move(client, admin, key, made2["number"], stage_id(board, "In progress")))
    assert await runs_of(pg_session_factory, made["id"]) == []
    assert await runs_of(pg_session_factory, made2["id"]) == []
    assert agent_env.jobs.queued == []


async def test_a_disabled_on_enter_agent_starts_nothing(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    _, admin, board, skill = await ai_board(client, pg_session_factory)
    key, stage = board["board"]["key"], stage_id(board, "In progress")
    await set_agents(client, admin, key, stage, [agent(skill, enabled=False)])
    made = await make_card(client, admin, key, stage_id=stage)
    assert await runs_of(pg_session_factory, made["id"]) == []


async def test_restoring_or_deleting_a_stage_starts_no_agent(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    _, admin, board, skill = await ai_board(client, pg_session_factory, stage="Backlog")
    key = board["board"]["key"]
    made = await make_card(client, admin, key, stage_id=stage_id(board, "To do"))
    url = f"{BOARDS}/{key}/cards/{made['number']}"
    # Restore back into its own stage, now given an on_enter agent.
    await set_agents(client, admin, key, stage_id(board, "To do"), [agent(skill)])
    ok(await client.post(f"{url}/archive", headers=admin.headers))
    ok(await client.post(f"{url}/restore", headers=admin.headers))
    assert await runs_of(pg_session_factory, made["id"]) == []
    # Deleting its stage moves it on to Backlog, which has an on_enter agent.
    stage_url = f"{BOARDS}/{key}/stages/{stage_id(board, 'To do')}"
    resp = await client.delete(
        stage_url,
        params={"move_to": stage_id(board, "Backlog")},
        headers=admin.headers,
    )
    assert resp.status_code in (200, 204), resp.text
    assert await runs_of(pg_session_factory, made["id"]) == []
    assert agent_env.jobs.queued == []


async def test_a_handover_and_a_bud_sent_back_start_no_agent(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    d = await desk(client, pg_session_factory)
    skill = await add_skill(pg_session_factory, d.org)
    for name in ("Ready for dev", "Ideas"):
        await set_agents(client, d.pm, d.key, d.stage(name), [agent(skill)])
    await ai_on(client, d.pm, d.key)
    url = await card(client, d, stage_id=d.stage("Shaping"), description_md="Why")
    card_id = ok(await client.get(url, headers=d.pm.headers))["id"]
    made = await handed(client, d.pm, url)
    assert ok(await client.get(url, headers=d.pm.headers))["stage_id"] == d.stage("Ready for dev")
    ok(await send_back(client, d.pm, bud_of(made)))
    assert ok(await client.get(url, headers=d.pm.headers))["stage_id"] == d.stage("Ideas")
    assert await runs_of(pg_session_factory, card_id) == []


async def test_moving_to_another_board_cancels_the_run_and_starts_the_targets(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    org, admin, board, skill = await ai_board(client, pg_session_factory)
    key = board["board"]["key"]
    other = await make_board(client, admin)
    other_key = other["board"]["key"]
    await set_agents(client, admin, other_key, stage_id(other, "Backlog"), [agent(skill)])
    await ai_on(client, admin, other_key)
    made = await make_card(client, admin, key, stage_id=stage_id(board, "In progress"))
    (first,) = await runs_of(pg_session_factory, made["id"])
    url = f"{BOARDS}/{key}/cards/{made['number']}/move-board"
    body = {"target_board_key": other_key, "stage_id": stage_id(other, "Backlog")}
    ok(await client.post(url, json=body, headers=admin.headers))
    old, new = await runs_of(pg_session_factory, made["id"])
    assert (old.id, old.status) == (first.id, BoardAgentRunStatus.CANCELED)
    assert old.error_message and "another board" in old.error_message
    assert [job for job, _ in agent_env.jobs.canceled] == [first.job_id]
    assert (new.status, new.stage_id) == (
        BoardAgentRunStatus.PENDING,
        uuid.UUID(stage_id(other, "Backlog")),
    )
