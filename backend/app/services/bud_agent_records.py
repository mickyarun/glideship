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

"""Run-end records for a BUD stage agent task.

:class:`app.services.bud_agent_handler.BudAgentSubject` builds on this: how a
run's end is written to the task row, the activity log, the timeline and the
Garden's ``agent_activity`` topic.
"""

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.bud_agent_task import AgentTaskStatus, BUDAgentTask
from app.services.agent_activity_logger import log_agent_activity
from app.services.bud_agent_state import BudAgentState
from app.services.event_bus import publish as _eb_publish
from app.services.job_utils import record_agent_timeline
from app.services.section_session import record_originating_session

logger = structlog.get_logger(__name__)


class BudAgentRecords(BudAgentState):
    """How a BUD agent task's run end is recorded."""

    async def record_success(self, db: AsyncSession, summary: dict[str, Any] | None) -> None:
        """Log completion, mark the task completed and keep its CLI session."""
        await log_agent_activity(
            db,
            org_id=self.org_id,
            event_type="skill_completed",
            skill_slug=self.skill_slug,
            message=f"Skill '{self.skill_slug}' completed for {self.task_type}",
            bud_id=self.bud_id,
            skill_id=self.task.skill_id,
            task_id=self.task_id,
            repo_id=self.repo_id,
            metadata_=summary,
            bud_number=self.bud_number,
            bud_title=self.bud_title,
        )
        self.task.status = AgentTaskStatus.COMPLETED
        self.task.result_summary = summary
        self.task.error_message = None
        await db.commit()
        # Chats on the same section ``--resume`` against this session.
        if self.session_section is not None and self.session_id is not None:
            await record_originating_session(
                org_id=self.org_id,
                bud_id=self.bud_id,
                section=self.session_section,
                session_id=self.session_id,
            )
        self.log_phase("result_saved", task_id=str(self.task_id), task_type=self.task_type)

    async def record_failure(
        self, db: AsyncSession, error: str, error_code: str | None = None
    ) -> None:
        """Log the provider's failure and mark the task failed (the job carries the code)."""
        await log_agent_activity(
            db,
            org_id=self.org_id,
            event_type="skill_failed",
            skill_slug=self.skill_slug,
            message=error,
            bud_id=self.bud_id,
            skill_id=self.task.skill_id,
            task_id=self.task_id,
            repo_id=self.repo_id,
            bud_number=self.bud_number,
            bud_title=self.bud_title,
        )
        self.task.status = AgentTaskStatus.FAILED
        self.task.error_message = error[:500]
        await db.commit()

    async def record_cancel(self, reason: str) -> None:
        """Flip a still-active task to failed with the cancel reason."""
        async with AsyncSessionLocal() as err_db:
            err_task = await err_db.get(BUDAgentTask, self.task_id)
            if err_task and err_task.status in (AgentTaskStatus.PENDING, AgentTaskStatus.RUNNING):
                err_task.status = AgentTaskStatus.FAILED
                err_task.error_message = reason[:500]
            await err_db.commit()
        await log_agent_activity(
            None,
            org_id=self.org_id,
            event_type="skill_failed",
            skill_slug=self.skill_slug,
            message=reason,
            bud_id=self.bud_id,
            task_id=self.task_id,
        )
        logger.info("bud_agent_job_cancelled", task_id=str(self.task_id), reason=reason)

    async def record_crash(self, exc: Exception) -> None:
        """Mark the task failed in a fresh session (the main one was rolled back)."""
        async with AsyncSessionLocal() as err_db:
            err_task = await err_db.get(BUDAgentTask, self.task_id)
            if err_task:
                err_task.status = AgentTaskStatus.FAILED
                err_task.error_message = str(exc)[:500]
            await err_db.commit()
        await log_agent_activity(
            None,
            org_id=self.org_id,
            event_type="skill_failed",
            skill_slug=self.skill_slug,
            message=str(exc)[:2000],
            bud_id=self.bud_id,
            task_id=self.task_id,
        )
        logger.exception("bud_agent_job_failed", task_id=str(self.task_id))

    async def after_success(self) -> None:
        """Record the timeline event from captured scalars (the session is closed)."""
        await record_agent_timeline(
            self.payload.org_id,
            self.payload.bud_id,
            "ai_agent_completed",
            skill_name=self.skill_slug,
            section=self.task_type,
            job_id=self.job_id,
        )

    def announce(self) -> None:
        """Re-publish ``skill_completed`` in case the first publish was lost.

        The first publish (inside ``log_agent_activity``) can be dropped if
        the socket blinked during the long run; by now the job topic proved
        it is alive. ``character.complete()`` is idempotent on the frontend.
        """
        topic = f"agent_activity:{self.org_id}"
        logger.info("agent_activity_republish", topic=topic, task_id=str(self.task_id))
        _eb_publish(
            topic,
            {
                "event_type": "skill_completed",
                "status": "completed",
                "message": f"Skill '{self.skill_slug}' completed for {self.task_type}",
                "skill_slug": self.skill_slug,
                "actor_name": self.skill_slug,
                "task_id": str(self.task_id),
                "repo_name": None,
                "bud_number": self.bud_number,
                "bud_title": self.bud_title,
                "impacted_repo_names": [],
                "created_at": "",
            },
        )
