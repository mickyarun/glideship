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

"""Data access for the agents on a board's stages, scoped to an organization."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_skill import AgentSkill
from app.models.board_agent import BoardAgentTrigger, BoardStageAgent
from app.repositories.base import BaseRepository


class BoardStageAgentRepository(BaseRepository[BoardStageAgent]):
    """Tenant-scoped repository for stage agents."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        super().__init__(BoardStageAgent, db, org_id=org_id)

    async def list_for_stage(
        self, board_id: uuid.UUID, stage_id: uuid.UUID
    ) -> list[tuple[BoardStageAgent, AgentSkill]]:
        """The stage's agents in run order, each with its skill."""
        stmt = self._scoped(
            select(BoardStageAgent, AgentSkill)
            .join(AgentSkill, AgentSkill.id == BoardStageAgent.skill_id)
            .where(BoardStageAgent.board_id == board_id, BoardStageAgent.stage_id == stage_id)
            .order_by(BoardStageAgent.execution_order)
        )
        return [(agent, skill) for agent, skill in (await self._db.execute(stmt)).all()]

    async def replace_for_stage(
        self, board_id: uuid.UUID, stage_id: uuid.UUID, agents: list[BoardStageAgent]
    ) -> list[BoardStageAgent]:
        """Make ``agents`` the stage's list; the stored rows, in the order given.

        An entry whose ``id`` is one of the stage's agents updates that row
        in place, keeping its id; the others are inserted (the entries are
        never added themselves when they name a row). The stage's agents not
        named are deleted; their runs keep their history.
        """
        stmt = self._scoped(
            select(BoardStageAgent).where(
                BoardStageAgent.board_id == board_id, BoardStageAgent.stage_id == stage_id
            )
        )
        current = {a.id: a for a in (await self._db.execute(stmt)).scalars().all()}
        kept = {a.id for a in agents if a.id in current}
        gone = current.keys() - kept
        if gone:
            await self._db.execute(
                delete(BoardStageAgent).where(
                    BoardStageAgent.org_id == self._org_id, BoardStageAgent.id.in_(gone)
                )
            )
        # Park the kept rows clear of the unique order and the one-on_enter
        # index, so a swap of orders or triggers can't clash midway.
        for parked, agent_id in enumerate(sorted(kept, key=str), start=1):
            current[agent_id].execution_order = -parked
            current[agent_id].trigger = BoardAgentTrigger.MANUAL
        await self._db.flush()
        stored: list[BoardStageAgent] = []
        for wanted in agents:
            row = current.get(wanted.id) if wanted.id in kept else None
            if row is None:
                self._db.add(wanted)
                stored.append(wanted)
                continue
            row.skill_id, row.execution_order = wanted.skill_id, wanted.execution_order
            row.trigger, row.enabled = wanted.trigger, wanted.enabled
            stored.append(row)
        await self._db.flush()
        return stored

    async def on_enter_agent(
        self, board_id: uuid.UUID, stage_id: uuid.UUID
    ) -> tuple[BoardStageAgent, AgentSkill] | None:
        """The stage's switched-on ``on_enter`` agent and its skill, if it has one."""
        stmt = self._scoped(
            select(BoardStageAgent, AgentSkill)
            .join(AgentSkill, AgentSkill.id == BoardStageAgent.skill_id)
            .where(
                BoardStageAgent.board_id == board_id,
                BoardStageAgent.stage_id == stage_id,
                BoardStageAgent.trigger == BoardAgentTrigger.ON_ENTER,
                BoardStageAgent.enabled.is_(True),
            )
        )
        row = (await self._db.execute(stmt)).first()
        return None if row is None else (row[0], row[1])

    async def get_in_board(
        self, board_id: uuid.UUID, agent_id: uuid.UUID
    ) -> tuple[BoardStageAgent, AgentSkill] | None:
        """One of the board's stage agents and its skill."""
        stmt = self._scoped(
            select(BoardStageAgent, AgentSkill)
            .join(AgentSkill, AgentSkill.id == BoardStageAgent.skill_id)
            .where(BoardStageAgent.board_id == board_id, BoardStageAgent.id == agent_id)
        )
        row = (await self._db.execute(stmt)).first()
        return None if row is None else (row[0], row[1])

    async def skills_by_ids(self, skill_ids: set[uuid.UUID]) -> dict[uuid.UUID, AgentSkill]:
        """The org's library skills among ``skill_ids``; others' ids are left out."""
        if not skill_ids:
            return {}
        stmt = select(AgentSkill).where(
            AgentSkill.org_id == self._org_id, AgentSkill.id.in_(skill_ids)
        )
        return {s.id: s for s in (await self._db.execute(stmt)).scalars().all()}
