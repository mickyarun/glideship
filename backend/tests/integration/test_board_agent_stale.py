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

"""Runs that can't still be going: restarts, stale runs, and starts racing a cap.

A restart fails pending and running runs and leaves finished ones. A run
past its deadline plus the grace is failed by the sweep (its board hears it,
its job is canceled) and doesn't hold its card when a new run starts. Two
starts racing at an org cap can't both pass.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.config import settings
from app.models.board_agent import BoardAgentRunStatus, BoardCardAgentRun
from app.repositories.board_agent_run_sweep import (
    INTERRUPTED,
    STALE,
    recover_stuck_board_agent_runs,
)
from app.services import event_bus
from app.services.boards.agents import trigger
from app.services.boards.agents.stale_sweep import sweep_once
from tests.integration.board_agent_setup import Setup, agent_card, start
from tests.integration.board_agent_support import AgentEnv, agent_env, runs_of
from tests.integration.board_api_support import make_card
from tests.integration.mcp_support import mcp_env
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration
__all__ = ["agent_env", "mcp_env"]


async def _age(factory: Factory, run_id: uuid.UUID, seconds: int, **values: object) -> None:
    """Make the run look ``seconds`` old."""
    then = datetime.now(UTC) - timedelta(seconds=seconds)
    async with factory() as db:
        await db.execute(
            update(BoardCardAgentRun)
            .where(BoardCardAgentRun.id == run_id)
            .values(created_at=then, **values)
        )
        await db.commit()


async def _second_card(client: AsyncClient, s: Setup) -> dict[str, object]:
    return await make_card(client, s.admin, s.key, "Second", stage_id=s.card["stage_id"])


async def test_a_restart_fails_active_runs_and_leaves_finished_ones(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory)
    agent_env.runner.reply("# PRD")
    await start(client, s)
    await agent_env.jobs.run_all()
    (done,) = await runs_of(pg_session_factory, s.card["id"])
    pending = await start(client, s)
    second = await _second_card(client, s)
    url = f"{s.card_url.rsplit('/', 1)[0]}/{second['number']}/agents/{s.agent_id}/run"
    running = (await client.post(url, headers=s.admin.headers)).json()
    async with pg_session_factory() as db:
        await db.execute(
            update(BoardCardAgentRun)
            .where(BoardCardAgentRun.id == uuid.UUID(running["run"]["id"]))
            .values(status=BoardAgentRunStatus.RUNNING)
        )
        await recover_stuck_board_agent_runs(db)
        await db.commit()
    runs = await runs_of(pg_session_factory, s.card["id"])
    runs += await runs_of(pg_session_factory, str(second["id"]))
    by_id = {str(r.id): r for r in runs}
    assert by_id[str(done.id)].status is BoardAgentRunStatus.COMPLETED
    for stuck in (pending["run"]["id"], running["run"]["id"]):
        assert (by_id[stuck].status, by_id[stuck].error_message) == (
            BoardAgentRunStatus.FAILED,
            INTERRUPTED,
        )


async def test_the_sweep_fails_a_stale_run_announces_it_and_stops_its_job(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory)
    started = await start(client, s)
    fresh = await _second_card(client, s)
    url = f"{s.card_url.rsplit('/', 1)[0]}/{fresh['number']}/agents/{s.agent_id}/run"
    young = (await client.post(url, headers=s.admin.headers)).json()
    cfg = settings.boards
    limit = cfg.agent_timeout_seconds + cfg.agent_stale_grace_seconds
    await _age(pg_session_factory, uuid.UUID(started["run"]["id"]), limit + 60)
    queue = event_bus.subscribe(f"board:{s.board_id}")
    try:
        assert await sweep_once() >= 1
        await asyncio.sleep(0)
        events = [queue.get_nowait()["data"] for _ in range(queue.qsize())]
    finally:
        event_bus.unsubscribe(f"board:{s.board_id}", queue)
    (stale,) = await runs_of(pg_session_factory, s.card["id"])
    assert (stale.status, stale.error_message) == (BoardAgentRunStatus.FAILED, STALE)
    (kept,) = await runs_of(pg_session_factory, str(fresh["id"]))
    assert str(kept.id) == young["run"]["id"] and kept.status is BoardAgentRunStatus.PENDING
    updates = [e["run"] for e in events if e["event"] == "agent_run_updated"]
    assert [(u["id"], u["status"]) for u in updates] == [(started["run"]["id"], "failed")]
    assert (started["job_id"], STALE) in agent_env.jobs.canceled


async def test_a_stale_run_does_not_hold_its_card(
    client: AsyncClient, pg_session_factory: Factory, agent_env: AgentEnv
) -> None:
    s = await agent_card(client, pg_session_factory)
    first = await start(client, s)
    started_at = datetime.now(UTC) - timedelta(days=1)
    await _age(
        pg_session_factory,
        uuid.UUID(first["run"]["id"]),
        2 * 86400,
        status=BoardAgentRunStatus.RUNNING,
        started_at=started_at,
    )
    second = await start(client, s)
    old, new = await runs_of(pg_session_factory, s.card["id"])
    assert (old.status, old.error_message) == (BoardAgentRunStatus.FAILED, STALE)
    assert str(new.id) == second["run"]["id"] and new.status is BoardAgentRunStatus.PENDING
    assert (first["job_id"], STALE) in agent_env.jobs.canceled


async def test_two_starts_racing_at_the_org_cap_cannot_both_pass(
    client: AsyncClient,
    pg_session_factory: Factory,
    agent_env: AgentEnv,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = await agent_card(client, pg_session_factory)
    other = await _second_card(client, s)
    monkeypatch.setattr(settings.boards, "agent_runs_per_org_max", 1)
    real = trigger.run_limit_reached

    async def counted_then_paused(*args: Any) -> str | None:
        # Give the other start every chance to count before this one claims.
        over = await real(*args)
        await asyncio.sleep(0.2)
        return over

    monkeypatch.setattr(trigger, "run_limit_reached", counted_then_paused)
    base = s.card_url.rsplit("/", 1)[0]
    urls = [f"{base}/{n}/agents/{s.agent_id}/run" for n in (s.card["number"], other["number"])]
    answers = await asyncio.gather(*(client.post(u, headers=s.admin.headers) for u in urls))
    assert sorted(r.status_code for r in answers) == [202, 429]
    runs = await runs_of(pg_session_factory, s.card["id"])
    runs += await runs_of(pg_session_factory, str(other["id"]))
    assert len(runs) == 1
