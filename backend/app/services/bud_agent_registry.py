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

"""Per-task-type registry for BUD stage agents: prompt builders and result handlers.

Adding a new agent type = add a builder + handler entry here.
"""

import uuid as uuid_mod
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.prompts.learning_prompt import build_learning_prompt
from app.models.bud import BUDDocument
from app.models.bud_agent_task import BUDAgentTask
from app.repositories.bud import BUDDesignRepository
from app.repositories.organization import OrganizationRepository
from app.services.agent_prompts import (
    build_code_review_prompt,
    build_prd_prompt,
    build_tech_arch_prompt,
    build_testing_prompt,
)
from app.services.agent_result_handlers import (
    handle_code_review_result,
    handle_learning_result,
    handle_prd_result,
    handle_tech_arch_result,
    handle_testing_result,
)
from app.services.ai_runner.capabilities import capabilities_for
from app.services.skill_loader import Skill

# ── Protocol for per-type prompt builders ─────────────────────────


class PromptBuilder(Protocol):
    """Protocol for building an agent prompt from BUD state."""

    async def __call__(
        self, bud: BUDDocument, skill: Skill, org_id: uuid_mod.UUID, db: Any
    ) -> tuple[str, str | None]:
        """Build the prompt and optional working directory.

        Returns:
            Tuple of (prompt_string, optional_working_dir).
        """
        ...


class ResultHandler(Protocol):
    """Protocol for handling agent output after Claude completes."""

    async def __call__(
        self,
        bud_id: uuid_mod.UUID,
        org_id: uuid_mod.UUID,
        output: str,
        task: BUDAgentTask,
        db: Any,
    ) -> dict[str, Any] | None:
        """Process agent output and persist results.

        Returns:
            Optional result_summary dict for the task row.
        """
        ...


# ── Registry ──────────────────────────────────────────────────────

PROMPT_BUILDERS: dict[str, PromptBuilder] = {
    "bud": build_prd_prompt,
    "tech_arch": build_tech_arch_prompt,
    "code_review": build_code_review_prompt,
    "testing": build_testing_prompt,
    "closed": build_learning_prompt,
}


async def provider_reads_files(db: AsyncSession, org_id: uuid_mod.UUID) -> bool:
    """Whether this org's provider has filesystem access."""
    org = await OrganizationRepository(db).get_by_id(org_id)
    if org is None:
        return True  # unknown org: keep today's behaviour, run_agent still guards
    return capabilities_for(org.ai_provider).supports_files


RESULT_HANDLERS: dict[str, ResultHandler] = {
    "bud": handle_prd_result,
    "tech_arch": handle_tech_arch_result,
    "code_review": handle_code_review_result,
    "testing": handle_testing_result,
    "closed": handle_learning_result,
}


async def fail_designs_for_bud(
    db: AsyncSession, org_id: uuid_mod.UUID, bud_id: uuid_mod.UUID
) -> None:
    """Mark all 'generating' design rows for a BUD as 'failed'."""
    await BUDDesignRepository(db, org_id=org_id).mark_generating_failed_for_bud(bud_id)


def skill_from_row(task: BUDAgentTask) -> Skill:
    """The task's skill row as a :class:`Skill`."""
    row = task.skill
    return Skill(
        name=row.name,
        slug=row.skill_slug,
        description=row.description,
        tools=row.tools,
        mcp_tools=row.mcp_tools,
        prompt=row.prompt,
        max_turns=row.max_turns or 0,
        model=row.model or "",
        effort=row.effort or "",
    )
