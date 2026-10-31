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

"""Starting stage-agent runs on cards: on entering a stage, and from the Run button.

Both need the board's ``ai_enabled`` switch on and no active run on the card
(the partial unique index decides, so two starts can't both win). The run
row is written with the request and its job is enqueued only after the
commit, so the job always finds its row. An ``on_enter`` start never fails
the move that caused it: with AI off, no agent, or a run already going, the
move goes ahead and nothing starts. ``ENTRY_RULES`` says which entries start
agents at all.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board import Board, BoardStage
from app.models.board_agent import BoardAgentTrigger, BoardCardAgentRun, BoardStageAgent
from app.models.board_card import BoardCard
from app.repositories.board_agent import BoardStageAgentRepository
from app.repositories.board_agent_run import BoardCardAgentRunRepository
from app.schemas.boards.agent import AgentRunAccepted
from app.services.after_commit import call_after_commit
from app.services.boards.access import CardAccess
from app.services.boards.agents.errors import AgentRunActiveError, BoardAiDisabledError
from app.services.boards.agents.queue import enqueue_after_commit, enqueue_now
from app.services.boards.agents.runs import queue_run_event
from app.services.boards.card_checks import check_open
from app.services.boards.errors import BoardItemNotFoundError, BoardRuleError
from app.services.boards.move_rules import ENTRY_RULES, EntryCause

AGENT_NOT_FOUND = "That agent isn't on this board."
AGENT_OFF = "That agent is switched off."
AGENT_ELSEWHERE = "That agent belongs to another stage; move the card there to run it."


def _values(
    card: BoardCard,
    agent: BoardStageAgent,
    trigger: BoardAgentTrigger,
    triggered_by: uuid.UUID | None,
) -> dict[str, object]:
    return {
        "card_id": card.id,
        "stage_id": agent.stage_id,
        "stage_agent_id": agent.id,
        "skill_id": agent.skill_id,
        "trigger": trigger,
        "triggered_by": triggered_by,
        "job_id": str(uuid.uuid4()),
    }


async def queue_entry_agents(
    db: AsyncSession,
    *,
    board: Board,
    card: BoardCard,
    stage: BoardStage,
    cause: EntryCause,
) -> BoardCardAgentRun | None:
    """Start the stage's ``on_enter`` agent for a card entering it, when everything allows.

    Call after the card's ``stage_id`` is set, inside the request that moves
    it; the caller commits. Returns the run, or None when nothing started.
    """
    if not ENTRY_RULES[cause].on_enter_agents or not board.ai_enabled:
        return None
    found = await BoardStageAgentRepository(db, org_id=card.org_id).on_enter_agent(
        board.id, stage.id
    )
    if found is None:
        return None
    agent, _skill = found
    runs = BoardCardAgentRunRepository(db, org_id=card.org_id)
    run = await runs.claim(_values(card, agent, BoardAgentTrigger.ON_ENTER, None))
    if run is None:
        return None
    queue_run_event(db, board.id, run)
    call_after_commit(db, enqueue_after_commit(run))
    return run


async def _agent_for(target: CardAccess, db: AsyncSession, agent_id: uuid.UUID) -> BoardStageAgent:
    """The board's agent ``agent_id``, checked that it can run on the card now."""
    access, card = target.access, target.card
    if not access.board.ai_enabled:
        raise BoardAiDisabledError()
    check_open(card)
    found = await BoardStageAgentRepository(db, org_id=access.org_id).get_in_board(
        access.board.id, agent_id
    )
    if found is None:
        raise BoardItemNotFoundError(AGENT_NOT_FOUND)
    agent = found[0]
    if not agent.enabled:
        raise BoardRuleError(AGENT_OFF)
    if agent.stage_id != card.stage_id:
        raise BoardRuleError(AGENT_ELSEWHERE)
    return agent


async def run_agent(db: AsyncSession, target: CardAccess, agent_id: uuid.UUID) -> AgentRunAccepted:
    """Start one of the stage's agents on the card (Run, or Retry after a failure).

    Raises:
        BoardAiDisabledError: The board's AI switch is off (409).
        AgentRunActiveError: The card already has a run going (409).
        BoardItemNotFoundError: No such agent on the board (404).
        BoardRuleError: The agent is off, or on another stage (422).
        BoardBusyError: The agent queue is full (503); the run is marked failed.
    """
    agent = await _agent_for(target, db, agent_id)
    access, card = target.access, target.card
    runs = BoardCardAgentRunRepository(db, org_id=access.org_id)
    run = await runs.claim(_values(card, agent, BoardAgentTrigger.MANUAL, access.user_id))
    if run is None:
        active = await runs.active_for_card(card.id)
        raise AgentRunActiveError(active.id if active else None)
    queue_run_event(db, access.board.id, run, actor_id=access.user_id, origin=access.origin)
    await db.commit()
    return await enqueue_now(db, access.board.id, run)
