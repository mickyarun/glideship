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

"""Loading a BUD stage agent task's rows for its run.

A task, BUD or skill that's gone, or a task type with no prompt builder,
fails the task here (and, for a design task, its generating designs) so
the UI stops waiting.
"""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bud_agent_task import AgentTaskStatus, BUDAgentTask
from app.repositories.bud import BUDRepository
from app.services.bud_agent_records import BudAgentRecords
from app.services.bud_agent_registry import PROMPT_BUILDERS, fail_designs_for_bud, skill_from_row

logger = structlog.get_logger(__name__)


class BudAgentLoader(BudAgentRecords):
    """Loads a BUD agent task, its BUD and skill."""

    async def _fail_task(self, db: AsyncSession, error: str) -> str:
        """Mark the task failed with ``error``, commit, and hand the error back."""
        self.task.status = AgentTaskStatus.FAILED
        self.task.error_message = error
        await db.commit()
        return error

    async def load(self, db: AsyncSession) -> str | None:
        """Load the task, its BUD and skill, and check a prompt builder exists."""
        task = await db.get(BUDAgentTask, self.task_id)
        if not task:
            logger.error(
                "bud_agent_task_not_found",
                task_id=str(self.task_id),
                job_id=self.job_id,
                org_id=str(self.org_id),
            )
            return "Agent task not found"
        # Defense-in-depth: verify task belongs to the expected org
        if task.org_id != self.org_id:
            return "Org mismatch"
        self._task = task
        bud = await BUDRepository(db, org_id=self.org_id).get_by_id(self.bud_id)
        if not bud:
            return await self._fail_task(db, "BUD not found")
        self._bud = bud
        if not task.skill:
            return await self._fail_task(db, "Skill not found")

        self.skill_slug = task.skill.skill_slug
        self.task_type = task.task_type
        self.bud_number = bud.bud_number
        self.bud_title = bud.title
        self.log_phase(
            "task_loaded",
            task_id=str(self.task_id),
            task_type=self.task_type,
            bud_id=str(self.bud_id),
            skill_slug=self.skill_slug,
        )
        self._skill = skill_from_row(task)

        if task.task_type not in PROMPT_BUILDERS:
            task.status = AgentTaskStatus.FAILED
            task.error_message = f"No prompt builder for task type: {task.task_type}"
            # Mark any associated design rows as failed so the UI stops spinning
            if task.task_type == "design":
                await fail_designs_for_bud(db, self.org_id, self.bud_id)
            await db.commit()
            return task.error_message
        return None
