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

"""Switching a board's AI off stops every run going on its cards.

Inside the request that switches it off, each pending or running run is
settled ``canceled`` with :data:`AI_SWITCHED_OFF`, recorded on its card as
an ``ai_run`` event and announced as ``agent_run_updated``; after the commit
its job is canceled (a queued one never starts, a running one goes through
the executor's cancel path and saves nothing). Locks: each card, then its
run, the order the card tools and a move between boards take.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board import Board
from app.models.board_agent import ACTIVE_RUN_STATUSES, BoardAgentRunStatus
from app.repositories.agent_skill import AgentSkillRepository
from app.repositories.board_agent_run import BoardCardAgentRunRepository
from app.repositories.board_card import BoardCardRepository
from app.services.boards.agents.apply import RunRefs, settle_canceled
from app.services.boards.agents.runs import queue_run_event, settle, stop_job_after_commit

AI_SWITCHED_OFF = "AI was switched off on this board, so this run stopped."


async def cancel_board_runs(db: AsyncSession, board: Board) -> int:
    """Cancel the board's active runs with the request; returns how many stopped."""
    runs = BoardCardAgentRunRepository(db, org_id=board.org_id)
    cards = BoardCardRepository(db, org_id=board.org_id)
    skills = AgentSkillRepository(db, org_id=board.org_id)
    stopped = 0
    for run_id in await runs.active_ids_on_board(board.id):
        run = await runs.get_by_id(run_id)
        card = await cards.get_by_id(run.card_id) if run else None
        if run is None or card is None:
            continue
        await cards.lock(card)
        await runs.lock(run)
        if run.status not in ACTIVE_RUN_STATUSES:
            continue
        skill = await skills.get_by_id(run.skill_id) if run.skill_id else None
        if skill is not None:
            await settle_canceled(
                db, RunRefs(board=board, card=card, run=run, skill=skill), AI_SWITCHED_OFF
            )
        else:
            settle(run, BoardAgentRunStatus.CANCELED, error=AI_SWITCHED_OFF)
            await db.flush()
            queue_run_event(db, board.id, run)
        stop_job_after_commit(db, run, AI_SWITCHED_OFF)
        stopped += 1
    return stopped
