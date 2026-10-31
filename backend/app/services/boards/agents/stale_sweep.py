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

"""The periodic sweep that fails stale card runs in every org.

A run past its deadline plus ``BOARDS_AGENT_STALE_GRACE_SECONDS`` is failed
in one statement (:func:`app.repositories.board_agent_run_sweep.fail_stale_runs`);
after the commit each one's board hears ``agent_run_updated`` and its job,
if it is somehow still going, is canceled. Runs every
``BOARDS_AGENT_STALE_SWEEP_SECONDS``; single-instance like the other sweeps.
"""

import structlog

from app.config import settings
from app.database import AsyncSessionLocal
from app.repositories.board_agent_run_sweep import STALE, fail_stale_runs
from app.services.boards.agents.runs import queue_run_event, stop_job_after_commit
from app.services.scheduling.tick_loop import run_tick_loop

logger = structlog.get_logger(__name__)


async def sweep_once() -> int:
    """Fail every stale run; returns how many."""
    cfg = settings.boards
    async with AsyncSessionLocal() as db:
        stale = await fail_stale_runs(
            db,
            timeout_seconds=cfg.agent_timeout_seconds,
            grace_seconds=cfg.agent_stale_grace_seconds,
        )
        for run, board_id in stale:
            queue_run_event(db, board_id, run)
            stop_job_after_commit(db, run, STALE)
        await db.commit()
    if stale:
        logger.info("board_agent_runs_stale_failed", count=len(stale))
    return len(stale)


async def _tick() -> None:
    await sweep_once()


async def run_forever() -> None:
    """Sweep every ``BoardsConfig.agent_stale_sweep_seconds`` until cancelled."""
    await run_tick_loop("board_agent_stale", settings.boards.agent_stale_sweep_seconds, _tick)
