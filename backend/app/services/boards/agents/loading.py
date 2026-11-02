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

"""Loading a card run's rows for its job, all inside the run's org.

A run no longer pending, or on a board whose AI was switched off, stops its
job as canceled (:class:`AgentRunCanceledError`). A run whose skill was deleted
fails with the usual notices. Ending a run on a fresh session (after the
job's own was rolled back) works without the skill too, so a run whose
skill was deleted mid-run still frees its card; if even that fails (the
database is unreachable), the stale-run sweep settles it later.
"""

import uuid
from collections.abc import Awaitable, Callable

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.board_agent import BoardAgentRunErrorCode, BoardAgentRunStatus, BoardCardAgentRun
from app.repositories.agent_skill import AgentSkillRepository
from app.repositories.board import BoardRepository
from app.repositories.board_agent_run import BoardCardAgentRunRepository
from app.repositories.board_card import BoardCardRepository
from app.services.agents.subject import AgentRunCanceledError
from app.services.boards.agents.apply import finish_canceled, finish_failed
from app.services.boards.agents.refs import RunRefs, RunRow

logger = structlog.get_logger(__name__)

# Settles a run on its own session; whether it did.
FreshFinish = Callable[[AsyncSession, RunRow], Awaitable[bool]]

RUN_NOT_FOUND = "Agent run not found"
RUN_NOT_PENDING = "This agent run was stopped before it started."
SKILL_GONE = "The skill this agent uses was deleted from the library."
AI_OFF = "AI was switched off on this board before the run started."


async def run_row(db: AsyncSession, run: BoardCardAgentRun) -> RunRow | None:
    """The run with its card, board and (unless deleted) skill; None without a card."""
    org_id = run.org_id
    card = await BoardCardRepository(db, org_id=org_id).get_by_id(run.card_id)
    board = await BoardRepository(db, org_id=org_id).get_by_id(card.board_id) if card else None
    if card is None or board is None:
        return None
    skills = AgentSkillRepository(db, org_id=org_id)
    skill = await skills.get_by_id(run.skill_id) if run.skill_id else None
    return RunRow(board=board, card=card, run=run, skill=skill)


async def load_refs(db: AsyncSession, org_id: uuid.UUID, run_id: uuid.UUID) -> RunRefs | str:
    """A pending run's rows, or why it can't start (a deleted skill fails the run).

    Raises:
        AgentRunCanceledError: The run isn't pending any more, or the board's AI is off
            (the run is then settled canceled).
    """
    run = await BoardCardAgentRunRepository(db, org_id=org_id).get_by_id(run_id)
    if run is None:
        return RUN_NOT_FOUND
    if run.status is not BoardAgentRunStatus.PENDING:
        raise AgentRunCanceledError(RUN_NOT_PENDING)
    row = await run_row(db, run)
    if row is None:
        return RUN_NOT_FOUND
    if row.skill is None:
        await finish_failed(db, row, SKILL_GONE, BoardAgentRunErrorCode.SKILL_GONE)
        return SKILL_GONE
    if not row.board.ai_enabled:
        await finish_canceled(db, row, AI_OFF)
        raise AgentRunCanceledError(AI_OFF)
    return RunRefs(board=row.board, card=row.card, run=row.run, skill=row.skill)


async def on_fresh_session(
    org_id: uuid.UUID,
    run_id: uuid.UUID,
    finish: FreshFinish,
) -> bool:
    """Run ``finish`` for the run on its own session; whether it settled the run.

    Never raises: a failure is logged and the stale-run sweep settles the run.
    """
    try:
        async with AsyncSessionLocal() as db:
            run = await BoardCardAgentRunRepository(db, org_id=org_id).get_by_id(run_id)
            row = None if run is None else await run_row(db, run)
            return False if row is None else await finish(db, row)
    except Exception:
        logger.exception("board_agent_run_settle_failed", run_id=str(run_id))
        return False
