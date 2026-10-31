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

"""The Run button: a 202 with the job, one active run per card, and what it needs.

Retry is the same call after a run failed.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.models.board_agent import BoardAgentRunStatus
from tests.integration.board_agent_setup import ai_board
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
    make_card,
    ok,
    person,
    put_role,
    stage_id,
)
from tests.integration.mcp_support import mcp_env
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration
__all__ = ["agent_env", "mcp_env"]


async def test_run_button_queues_a_run_and_a_second_one_is_409(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    org, admin, board, _ = await ai_board(client, pg_session_factory, stage="Backlog")
    key, stage = board["board"]["key"], stage_id(board, "To do")
    manual = await add_skill(pg_session_factory, org, name="Notes")
    (stored,) = await set_agents(client, admin, key, stage, [agent(manual, "manual")])
    editor = await person(pg_session_factory, org)
    await put_role(client, admin, key, editor.id, "editor")
    made = await make_card(client, admin, key, stage_id=stage)
    url = f"{BOARDS}/{key}/cards/{made['number']}/agents/{stored['id']}/run"
    accepted = ok(await client.post(url, headers=editor.headers), 202)
    assert accepted["run"]["status"] == "pending"
    assert accepted["run"]["triggered_by"] == str(editor.id)
    assert [job for job, _ in agent_env.jobs.queued] == [accepted["job_id"]]
    again = await client.post(url, headers=editor.headers)
    assert again.status_code == 409
    assert again.json()["code"] == "AGENT_RUN_ACTIVE"
    assert again.json()["run_id"] == accepted["run"]["id"]


async def test_run_button_needs_ai_an_editor_and_the_cards_stage(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    org, admin, board, skill = await ai_board(client, pg_session_factory, stage="Backlog")
    key = board["board"]["key"]
    (stored,) = await set_agents(
        client, admin, key, stage_id(board, "To do"), [agent(skill, "manual")]
    )
    viewer = await person(pg_session_factory, org)
    await put_role(client, admin, key, viewer.id, "viewer")
    on_stage = await make_card(client, admin, key, stage_id=stage_id(board, "To do"))
    elsewhere = await make_card(client, admin, key, stage_id=stage_id(board, "Done"))
    run = f"agents/{stored['id']}/run"
    url = f"{BOARDS}/{key}/cards/{on_stage['number']}/{run}"
    assert (await client.post(url, headers=viewer.headers)).status_code == 403
    off_stage = f"{BOARDS}/{key}/cards/{elsewhere['number']}/{run}"
    assert (await client.post(off_stage, headers=admin.headers)).status_code == 422
    missing = f"{BOARDS}/{key}/cards/{on_stage['number']}/agents/{uuid.uuid4()}/run"
    assert (await client.post(missing, headers=admin.headers)).status_code == 404
    await ai_on(client, admin, key, False)
    off = await client.post(url, headers=admin.headers)
    assert (off.status_code, off.json()["code"]) == (409, "AI_DISABLED")
    assert agent_env.jobs.queued == []


async def test_a_full_queue_fails_the_run_with_503_and_retry_after(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    _, admin, board, skill = await ai_board(client, pg_session_factory, stage="Backlog")
    key, stage = board["board"]["key"], stage_id(board, "To do")
    (stored,) = await set_agents(client, admin, key, stage, [agent(skill, "manual")])
    made = await make_card(client, admin, key, stage_id=stage)
    agent_env.jobs.full = True
    url = f"{BOARDS}/{key}/cards/{made['number']}/agents/{stored['id']}/run"
    resp = await client.post(url, headers=admin.headers)
    assert resp.status_code == 503
    assert resp.headers["retry-after"]
    (run,) = await runs_of(pg_session_factory, made["id"])
    assert run.status is BoardAgentRunStatus.FAILED
