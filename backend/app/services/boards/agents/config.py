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

"""A stage's agents: reading them, and replacing the whole list (board admins).

Any skill in the org's library may run on a stage, custom ones included; a
skill from another org is refused. A stage holds at most one ``on_enter``
agent (one active run per card means a second could never start) and each
``order`` once. Replacing the list keeps past runs: they keep their skill and
lose only the link to the removed agent row.
"""

import uuid
from collections import Counter

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_skill import AgentSkill
from app.models.board_agent import BoardAgentTrigger, BoardStageAgent
from app.repositories.board_agent import BoardStageAgentRepository
from app.repositories.board_stage import BoardStageRepository
from app.schemas.boards.agent import CardAgents, StageAgentRead, StageAgentWrite
from app.services.boards.access import BoardAccess, CardAccess
from app.services.boards.agents.errors import SkillNotInLibraryError
from app.services.boards.agents.runs import card_runs
from app.services.boards.constants import AGENT_OUTPUT_KINDS, DEFAULT_AGENT_OUTPUT_KIND
from app.services.boards.errors import BoardItemNotFoundError, BoardRuleError
from app.services.boards.live import BoardChanges, BoardSocketEvent
from app.services.boards.stage_service import STAGE_NOT_FOUND

ONE_ON_ENTER = "A stage can start only one agent when a card enters it."
ORDER_TAKEN = "Give each agent on the stage its own order."


def _read(agent: BoardStageAgent, skill: AgentSkill) -> StageAgentRead:
    return StageAgentRead(
        id=agent.id,
        stage_id=agent.stage_id,
        skill_id=skill.id,
        skill_name=skill.name,
        skill_slug=skill.skill_slug,
        agent_type=skill.agent_type,
        output_kind=AGENT_OUTPUT_KINDS.get(skill.agent_type, DEFAULT_AGENT_OUTPUT_KIND),
        trigger=agent.trigger,
        enabled=agent.enabled,
        order=agent.execution_order,
    )


async def list_stage_agents(
    db: AsyncSession, access: BoardAccess, stage_id: uuid.UUID
) -> list[StageAgentRead]:
    """The stage's agents in run order."""
    stages = BoardStageRepository(db, org_id=access.org_id)
    if await stages.get_in_board(access.board.id, stage_id) is None:
        raise BoardItemNotFoundError(STAGE_NOT_FOUND)
    repo = BoardStageAgentRepository(db, org_id=access.org_id)
    return [_read(a, s) for a, s in await repo.list_for_stage(access.board.id, stage_id)]


async def card_agents(db: AsyncSession, target: CardAccess) -> CardAgents:
    """The card's AI panel: its stage's switched-on agents and its runs."""
    access, card = target.access, target.card
    repo = BoardStageAgentRepository(db, org_id=access.org_id)
    agents = [
        _read(a, s)
        for a, s in await repo.list_for_stage(access.board.id, card.stage_id)
        if a.enabled
    ]
    runs, active = await card_runs(db, target)
    return CardAgents(ai_enabled=access.board.ai_enabled, agents=agents, runs=runs, active=active)


def _check_shape(body: list[StageAgentWrite]) -> None:
    if sum(1 for a in body if a.trigger is BoardAgentTrigger.ON_ENTER) > 1:
        raise BoardRuleError(ONE_ON_ENTER)
    if any(n > 1 for n in Counter(a.order for a in body).values()):
        raise BoardRuleError(ORDER_TAKEN)


async def replace_stage_agents(
    db: AsyncSession, access: BoardAccess, stage_id: uuid.UUID, body: list[StageAgentWrite]
) -> list[StageAgentRead]:
    """Make ``body`` the stage's agents; the board hears ``stage_agents_changed``.

    Raises:
        BoardItemNotFoundError: The stage isn't on this board (404).
        BoardRuleError: Two ``on_enter`` agents, or a repeated order (422).
        SkillNotInLibraryError: A skill isn't in the org's library (422).
    """
    _check_shape(body)
    stages = BoardStageRepository(db, org_id=access.org_id)
    if await stages.lock(access.board.id, stage_id) is None:
        raise BoardItemNotFoundError(STAGE_NOT_FOUND)
    repo = BoardStageAgentRepository(db, org_id=access.org_id)
    wanted = {a.skill_id for a in body}
    skills = await repo.skills_by_ids(wanted)
    missing = sorted(wanted - skills.keys(), key=str)
    if missing:
        raise SkillNotInLibraryError(missing)
    rows = [
        BoardStageAgent(
            org_id=access.org_id,
            board_id=access.board.id,
            stage_id=stage_id,
            skill_id=a.skill_id,
            execution_order=a.order,
            trigger=a.trigger,
            enabled=a.enabled,
            created_by=access.user_id,
        )
        for a in sorted(body, key=lambda a: a.order)
    ]
    await repo.replace_for_stage(access.board.id, stage_id, rows)
    result = [_read(row, skills[row.skill_id]) for row in rows]
    changes = BoardChanges.of(access)
    changes.emit(BoardSocketEvent.STAGE_AGENTS_CHANGED, stage_id=str(stage_id))
    await changes.commit(db)
    return result
