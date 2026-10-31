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

"""Loading a card run's rows for its job, all inside the run's org."""

import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.board_agent import BoardAgentRunStatus, BoardCardAgentRun
from app.repositories.agent_skill import AgentSkillRepository
from app.repositories.board import BoardRepository
from app.repositories.board_agent_run import BoardCardAgentRunRepository
from app.repositories.board_card import BoardCardRepository
from app.services.boards.agents.apply import RunRefs, finish_canceled
from app.services.boards.agents.runs import settle

RUN_NOT_FOUND = "Agent run not found"
RUN_NOT_PENDING = "This agent run was stopped before it started."
SKILL_GONE = "The skill this agent uses was deleted from the library."
AI_OFF = "AI was switched off on this board before the run started."


async def _rows(db: AsyncSession, run: BoardCardAgentRun) -> RunRefs | str:
    """The run with its card, board and skill, or why one of them is missing."""
    org_id = run.org_id
    card = await BoardCardRepository(db, org_id=org_id).get_by_id(run.card_id)
    board = await BoardRepository(db, org_id=org_id).get_by_id(card.board_id) if card else None
    if card is None or board is None:
        return RUN_NOT_FOUND
    skills = AgentSkillRepository(db, org_id=org_id)
    skill = await skills.get_by_id(run.skill_id) if run.skill_id else None
    if skill is None:
        return SKILL_GONE
    return RunRefs(board=board, card=card, run=run, skill=skill)


async def load_refs(db: AsyncSession, org_id: uuid.UUID, run_id: uuid.UUID) -> RunRefs | str:
    """A pending run's rows, or why it can't start (settling it when it was still pending)."""
    run = await BoardCardAgentRunRepository(db, org_id=org_id).get_by_id(run_id)
    if run is None:
        return RUN_NOT_FOUND
    if run.status is not BoardAgentRunStatus.PENDING:
        return RUN_NOT_PENDING
    refs = await _rows(db, run)
    if isinstance(refs, str):
        # Without a skill there's nothing to name in the card's history.
        settle(run, BoardAgentRunStatus.FAILED, error=refs)
        await db.commit()
        return refs
    if not refs.board.ai_enabled:
        await finish_canceled(db, refs, AI_OFF)
        return AI_OFF
    return refs


async def on_fresh_session(
    org_id: uuid.UUID,
    run_id: uuid.UUID,
    finish: Callable[[AsyncSession, RunRefs, str], Awaitable[object]],
    message: str,
) -> None:
    """Run ``finish`` for the run on its own session (after the job's one was rolled back)."""
    async with AsyncSessionLocal() as db:
        run = await BoardCardAgentRunRepository(db, org_id=org_id).get_by_id(run_id)
        refs = None if run is None else await _rows(db, run)
        if isinstance(refs, RunRefs):
            await finish(db, refs, message)
