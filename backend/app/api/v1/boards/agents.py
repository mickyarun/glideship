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

"""Stage agents (set up by board admins), and running them on a card (editors)."""

import uuid

from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.boards import _access as can
from app.config import settings
from app.core.deps import get_db
from app.schemas.boards.agent import (
    AgentRunAccepted,
    AgentRunRead,
    CardAgents,
    StageAgentRead,
    StageAgentWrite,
    StageSkillRead,
)
from app.services.boards.access import BoardAccess, CardAccess
from app.services.boards.agents import cancel, config, library, trigger

router = APIRouter(tags=["boards"])

STAGE_AGENTS = "/{key}/stages/{stage_id}/agents"
CARD_AGENTS = "/{key}/cards/{number}/agents"


@router.get("/{key}/skills", response_model=list[StageSkillRead])
async def list_stage_skills(
    access: BoardAccess = Depends(can.configure_agents_read),
    db: AsyncSession = Depends(get_db),
) -> list[StageSkillRead]:
    """The org's skills a stage can run, the suggested board skills first (board admins)."""
    return await library.stage_skills(db, access)


@router.get(STAGE_AGENTS, response_model=list[StageAgentRead])
async def list_stage_agents(
    stage_id: uuid.UUID,
    access: BoardAccess = Depends(can.configure_agents_read),
    db: AsyncSession = Depends(get_db),
) -> list[StageAgentRead]:
    """The stage's agents in run order, for the board's AI settings."""
    return await config.list_stage_agents(db, access, stage_id)


@router.put(STAGE_AGENTS, response_model=list[StageAgentRead])
async def replace_stage_agents(
    stage_id: uuid.UUID,
    body: list[StageAgentWrite] = Body(..., max_length=settings.boards.stage_agents_max),
    access: BoardAccess = Depends(can.configure_agents),
    db: AsyncSession = Depends(get_db),
) -> list[StageAgentRead]:
    """Replace the stage's agents with ``body`` (skills from the org's library)."""
    return await config.replace_stage_agents(db, access, stage_id, body)


@router.get(CARD_AGENTS, response_model=CardAgents)
async def card_agents(
    target: CardAccess = Depends(can.view_card), db: AsyncSession = Depends(get_db)
) -> CardAgents:
    """The card's AI panel: what Run offers on its stage, its latest runs and the active one."""
    return await config.card_agents(db, target)


@router.post(
    f"{CARD_AGENTS}/{{agent_id}}/run",
    response_model=AgentRunAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_card_agent(
    agent_id: uuid.UUID,
    target: CardAccess = Depends(can.run_agent),
    db: AsyncSession = Depends(get_db),
) -> AgentRunAccepted:
    """Start one of the card's stage agents (also Retry); follow ``job_id``.

    409 ``AI_DISABLED`` when the board's AI is off, 409 ``AGENT_RUN_ACTIVE``
    when the card already has a run going.
    """
    return await trigger.run_agent(db, target, agent_id)


@router.post(f"{CARD_AGENTS}/runs/{{run_id}}/cancel", response_model=AgentRunRead)
async def cancel_card_agent_run(
    run_id: uuid.UUID,
    target: CardAccess = Depends(can.run_agent),
    db: AsyncSession = Depends(get_db),
) -> AgentRunRead:
    """Cancel a pending or running run on the card (editors); 409 once it has finished."""
    return await cancel.cancel_run(db, target, run_id)
