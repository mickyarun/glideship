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

"""Run caps: per person from the Run button (429), per org on entering a stage (a failed run)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.config import settings
from app.models.board_agent import BoardAgentRunStatus
from app.services.boards.agents.limits import ORG_LIMIT
from tests.integration.board_agent_setup import agent_card, ai_board, move, start
from tests.integration.board_agent_support import AgentEnv, agent_env, runs_of
from tests.integration.board_api_support import make_card, ok, stage_id
from tests.integration.mcp_support import mcp_env
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration
__all__ = ["agent_env", "mcp_env"]


async def test_a_person_over_their_cap_is_told_to_wait(
    client: AsyncClient,
    pg_session_factory: Factory,
    agent_env: AgentEnv,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings.boards, "agent_runs_per_user_max", 1)
    s = await agent_card(client, pg_session_factory)
    await start(client, s)
    url = f"{s.card_url.rsplit('/', 1)[0]}"
    second = await make_card(client, s.admin, s.key, "Second", stage_id=s.card["stage_id"])
    resp = await client.post(
        f"{url}/{second['number']}/agents/{s.agent_id}/run", headers=s.admin.headers
    )
    assert resp.status_code == 429, resp.text
    assert resp.json()["code"] == "AGENT_RUN_LIMIT" and resp.headers["Retry-After"]
    assert await runs_of(pg_session_factory, second["id"]) == []


async def test_an_entry_over_the_org_cap_records_a_failed_run_and_queues_nothing(
    client: AsyncClient,
    pg_session_factory: Factory,
    agent_env: AgentEnv,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _org, admin, board, _skill = await ai_board(client, pg_session_factory)
    monkeypatch.setattr(settings.boards, "agent_runs_per_org_max", 0)
    key = board["board"]["key"]
    card = await make_card(client, admin, key, "Moves", stage_id=stage_id(board, "To do"))
    ok(await move(client, admin, key, card["number"], stage_id(board, "In progress")))
    (run,) = await runs_of(pg_session_factory, card["id"])
    assert run.status is BoardAgentRunStatus.FAILED and run.error_message == ORG_LIMIT
    assert run.triggered_by == admin.id
    assert agent_env.jobs.queued == []
