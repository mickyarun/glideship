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

"""The agent work a BUD's new status starts, from the stage mappings.

Shared by the status PATCH and handover landing. Looks up which agent the
new status runs (``agent_skill_bud_stages``) and asks for it through
:func:`create_agent_task_for_stage`, which creates the task row, commits
and enqueues the job.
"""

import uuid
from dataclasses import dataclass

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bud import BUDDesignStatus, BUDDocument, BUDStatus
from app.repositories.bud import BUDDesignRepository
from app.repositories.organization import OrganizationRepository
from app.services.bud_agent_trigger import create_agent_task_for_stage, should_auto_generate_phase
from app.services.bud_code_review_status import get_pr_status_summary
from app.services.org_settings import is_uat_enabled

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class StageJobsOutcome:
    """What the caller still has to do after :func:`run_stage_jobs`.

    ``design_available``: the BUD just entered design with generation on and
    no ready designs, so the client may start generating them.
    ``stopped``: a stage rule ended the work early (phase switched off, no
    open PR for code review, or the testing rule decided); the status PATCH
    then skips its re-estimation, as it always has.
    """

    design_available: bool = False
    stopped: bool = False


async def run_stage_jobs(
    db: AsyncSession,
    org_id: uuid.UUID,
    bud: BUDDocument,
    old_status: BUDStatus,
    new_status: BUDStatus,
    *,
    triggered_by: uuid.UUID,
) -> StageJobsOutcome:
    """Ask for the agent ``new_status`` runs, when the BUD's phase switch allows it."""
    # The phase opt-in gates everything that follows, the design hint too:
    # the client treats that hint as "start generating" (External-LLM mode).
    phase_key = new_status.value
    phases = bud.auto_generate_phases or {}
    phase_auto_generate = should_auto_generate_phase(phases, phase_key)

    design_available = False
    if new_status == BUDStatus.DESIGN and old_status != BUDStatus.DESIGN and phase_auto_generate:
        design_repo = BUDDesignRepository(db, org_id=org_id)
        ready_count = await design_repo.count_by_status(bud.id, BUDDesignStatus.READY)
        design_available = ready_count == 0

    if new_status == old_status:
        return StageJobsOutcome(design_available=design_available)
    stopped = StageJobsOutcome(design_available=design_available, stopped=True)

    if not phase_auto_generate:
        logger.info(
            "stage_agent_skip_auto_generate_off",
            bud_id=str(bud.id),
            from_status=str(old_status),
            to_status=str(new_status),
            phase_key=phase_key,
            phases=phases,
        )
        return stopped

    # The code review agent only posts feedback on open PRs; with none
    # (all merged, or none raised yet) it waits for the PR webhook.
    if new_status == BUDStatus.CODE_REVIEW:
        repo_statuses = await get_pr_status_summary(db, org_id, bud)
        if not any(r["pr_state"] == "open" for r in repo_statuses):
            logger.info(
                "code_review_agent_skip_no_open_prs",
                bud_id=str(bud.id),
                from_status=str(old_status),
                pr_states=[r["pr_state"] for r in repo_statuses],
            )
            return stopped

    # Entering testing: existing cases are kept; with none, the QA agent is
    # forced past the content guard (a stale "0 + 0" test plan isn't work).
    if new_status == BUDStatus.TESTING:
        if bud.qa_automation_cases or bud.qa_manual_cases:
            logger.info(
                "testing_agent_skip_cases_exist",
                bud_id=str(bud.id),
                auto_count=len(bud.qa_automation_cases or []),
                manual_count=len(bud.qa_manual_cases or []),
            )
            return stopped
        await create_agent_task_for_stage(
            bud, str(new_status), org_id, db, triggered_by=triggered_by, force=True
        )
        return stopped

    # Back to code review from a later stage re-runs the review; which
    # stages count as later depends on whether the org uses UAT.
    org = await OrganizationRepository(db).get_by_id(org_id)
    force_from_stages: list[BUDStatus] = [BUDStatus.TESTING]
    if is_uat_enabled(org.config if org else None):
        force_from_stages.append(BUDStatus.UAT)
    force = new_status == BUDStatus.CODE_REVIEW and old_status in force_from_stages
    await create_agent_task_for_stage(
        bud, str(new_status), org_id, db, triggered_by=triggered_by, force=force
    )
    return StageJobsOutcome(design_available=design_available)
