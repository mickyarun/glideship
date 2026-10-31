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

"""Unified BUD agent task handler.

Single handler for all BUD-level agent tasks (PRD, tech arch, code review).
Dispatches to per-type prompt builders and result handlers via an extensible
registry (`bud_agent_registry`). Adding a new agent type = add a builder + handler entry.

The run itself goes through the shared executor
(:func:`app.services.agents.executor.execute_agent_run`); this module is the
BUD side of it, :class:`BudAgentSubject`.
"""

import uuid as uuid_mod
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bud_agent_task import AgentTaskStatus, BUDAgentTask
from app.models.tracked_repository import TrackedRepository
from app.repositories.bud import BUDRepository
from app.schemas.bud_constants import BUD_AGENT_SECTIONS
from app.schemas.jobs import BUDAgentTaskPayload
from app.services.agent_activity_logger import log_agent_activity
from app.services.agent_phase_support import PHASES_NAVIGABLE_BY_GRAPH
from app.services.agents.executor import execute_agent_run
from app.services.agents.subject import AgentLaunch, AgentPrompt, AgentRunRef
from app.services.bud_agent_records import BudAgentRecords
from app.services.bud_agent_registry import (
    PROMPT_BUILDERS,
    RESULT_HANDLERS,
    fail_designs_for_bud,
    provider_reads_files,
    skill_from_row,
)
from app.services.bud_agent_retry import maybe_retry_on_git_auth_failure
from app.services.bud_repo_paths import confirmed_repo_paths
from app.services.claude_runner import (
    NO_REPO_CONTEXT,
    ClaudeRunnerConfig,
    ClaudeRunResult,
    MCPServerConfig,
    ProgressCallback,
)
from app.services.github_remote_refresh import refresh_origin_tokens
from app.services.job_utils import build_mcp_config
from app.services.section_session import mint_session_id

logger = structlog.get_logger(__name__)

__all__ = ["PROMPT_BUILDERS", "RESULT_HANDLERS", "BudAgentSubject", "handle_bud_agent_job"]


class BudAgentSubject(BudAgentRecords):
    """A BUD stage agent task, run through the shared executor."""

    def log_phase(self, phase: str, **fields: Any) -> None:
        """Log one step under ``bud_agent_phase``."""
        logger.info("bud_agent_phase", phase=phase, **fields)

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
                await fail_designs_for_bud(db, self.bud_id)
            await db.commit()
            return task.error_message
        return None

    async def build_prompt(self, db: AsyncSession) -> AgentPrompt:
        """Dispatch to the task type's prompt builder."""
        builder = PROMPT_BUILDERS[self.task_type]
        text, working_dir = await builder(self.bud, self.skill, self.org_id, db)
        return AgentPrompt(text=text, working_dir=working_dir)

    def mcp_grant(self) -> MCPServerConfig | None:
        """An org-wide internal token advertising the skill's MCP tools."""
        mcp: MCPServerConfig | None = build_mcp_config(
            org_id=str(self.org_id),
            tool_names=self.skill.mcp_tools if self.skill.mcp_tools else None,
        )
        return mcp

    def _session_for_run(self) -> tuple[uuid_mod.UUID | None, bool]:
        """The CLI session id to use, and whether it resumes an earlier one.

        Agents owning a BUD section that chat resumes get a session id; a
        re-run with ``resume_session_id`` resumes that session instead of
        minting one, keeping the prompt cache warm.
        """
        self.session_section = BUD_AGENT_SECTIONS.get(self.task_type)
        if self.session_section is None:
            return None, False
        if self.task.resume_session_id is not None:
            return self.task.resume_session_id, True
        return mint_session_id(), False

    async def prepare(
        self, db: AsyncSession, prompt: AgentPrompt, mcp: MCPServerConfig | None
    ) -> AgentLaunch:
        """Build the runner config, log the invocation and mark the task running."""
        self.session_id, is_resume = self._session_for_run()
        config = ClaudeRunnerConfig(
            max_turns=max(self.skill.max_turns, 0),
            timeout_seconds=600,
            mcp=mcp,
            model=self.skill.model or None,
            effort=self.skill.effort or None,
            cli_session_id=str(self.session_id) if self.session_id is not None else None,
            is_resume=is_resume,
        )
        # Code review needs JSON output
        if self.task_type == "code_review":
            config.output_format = "json"

        working_dir = prompt.working_dir
        if working_dir:
            repo_row = await db.execute(
                select(TrackedRepository.id).where(
                    TrackedRepository.path == working_dir,
                    TrackedRepository.org_id == self.org_id,
                )
            )
            self.repo_id = repo_row.scalar_one_or_none()

        # A separate session, so the row is visible now rather than after
        # the run (which can take minutes) commits.
        await log_agent_activity(
            None,
            org_id=self.org_id,
            event_type="skill_invoked",
            skill_slug=self.skill_slug,
            message=f"Skill '{self.skill_slug}' invoked for {self.task_type}",
            bud_id=self.bud_id,
            skill_id=self.task.skill_id,
            task_id=self.task_id,
            repo_id=self.repo_id,
            bud_number=self.bud_number,
            bud_title=self.bud_title,
        )
        self.task.status = AgentTaskStatus.RUNNING
        await db.commit()
        self.log_phase(
            "claude_invoked",
            task_id=str(self.task_id),
            task_type=self.task_type,
            bud_id=str(self.bud_id),
            skill_slug=self.skill_slug,
        )

        # Re-stamp every confirmed repo's ``origin`` with a fresh
        # installation token right before spawn (App tokens expire after an
        # hour). Best-effort: the agent may surface an auth error itself.
        self.repo_paths = confirmed_repo_paths(self.bud, fallback=working_dir)
        if self.repo_paths:
            await refresh_origin_tokens(working_dirs=self.repo_paths, org_id=self.org_id, db=db)

        # Builders that run purely against the LLM return no working dir;
        # map it to the explicit no-repo sentinel.
        spawn_cwd: str = working_dir if working_dir else NO_REPO_CONTEXT
        if (
            working_dir
            and self.task_type in PHASES_NAVIGABLE_BY_GRAPH
            and not await provider_reads_files(db, self.org_id)
        ):
            spawn_cwd = NO_REPO_CONTEXT
        return AgentLaunch(config=config, spawn_cwd=spawn_cwd)

    async def review(
        self,
        db: AsyncSession,
        result: ClaudeRunResult,
        prompt: AgentPrompt,
        launch: AgentLaunch,
        progress: ProgressCallback,
    ) -> ClaudeRunResult:
        """One automatic retry when git/gh returned an auth rejection."""
        return await maybe_retry_on_git_auth_failure(
            result=result,
            prompt=prompt.text,
            spawn_cwd=launch.spawn_cwd,
            working_dir=prompt.working_dir,
            repo_paths=self.repo_paths,
            config=launch.config,
            progress_callback=progress,
            org_id=self.org_id,
            bud_id=self.bud_id,
            task_id=self.task_id,
            skill_id=self.task.skill_id,
            skill_slug=self.skill_slug,
            repo_id=self.repo_id,
            db=db,
        )

    async def handle_output(self, db: AsyncSession, output: str) -> dict[str, Any] | None:
        """Refresh the BUD, then dispatch to the task type's result handler.

        The agent may have written the BUD through MCP in other sessions, and
        this session's instance is stale (``expire_on_commit=False``); one
        refresh here covers every result handler and downstream step.
        """
        await db.refresh(self.bud)
        handler = RESULT_HANDLERS.get(self.task_type)
        if handler is None:
            return None
        return await handler(self.bud_id, self.org_id, output, self.task, db)


async def handle_bud_agent_job(job_id: str, raw_payload: dict[str, Any]) -> None:
    """Unified handler for all BUD-level agent tasks.

    Loads the task from DB, dispatches to the appropriate prompt builder,
    runs the agent, then dispatches to the result handler.
    """
    payload = BUDAgentTaskPayload(**raw_payload)
    subject = BudAgentSubject(job_id, payload)
    run = AgentRunRef(org_id=subject.org_id, run_id=subject.task_id)
    await execute_agent_run(job_id, run, subject)
