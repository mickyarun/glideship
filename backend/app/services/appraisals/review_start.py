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

"""Opening the end-of-period review, and moving on people who skip their self-score.

HR starts the review once the period is over: the cycle moves to
reviewing, everyone enrolled gets their self-review, the period's facts
are gathered and saved, and AI-mode people are queued for a period
summary. Goals lock from here. Anyone who hasn't submitted a self-score
by its due date moves on to their manager, who scores from scratch.
"""

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import AppraisalStatus, CycleStatus
from app.repositories.appraisal import AppraisalRepository
from app.repositories.appraisal_cycle import AppraisalCycleRepository
from app.services.appraisals.errors import (
    AppraisalConflictError,
    AppraisalNotFoundError,
)
from app.services.appraisals.org_clock import org_today
from app.services.appraisals.period_facts import save_period_facts


async def start_review(db: AsyncSession, org_id: uuid.UUID, cycle_id: uuid.UUID) -> int:
    """Open the self-reviews; how many people got one."""
    cycle = await AppraisalCycleRepository(db, org_id=org_id).get_by_id(cycle_id)
    if cycle is None:
        raise AppraisalNotFoundError("Cycle not found.")
    if cycle.status is not CycleStatus.ACTIVE:
        raise AppraisalConflictError("Only a running cycle that hasn't started its review can.")
    if await org_today(db, org_id) <= cycle.period_end:
        raise AppraisalConflictError("The review opens once the period is over.")
    repo = AppraisalRepository(db, org_id=org_id)
    appraisals = [
        a for a in await repo.for_cycle(cycle.id) if a.status is AppraisalStatus.ENROLLED
    ]
    profiles = await repo.profiles_by_id([a.profile_id for a in appraisals])
    for appraisal in appraisals:
        profile = profiles.get(appraisal.profile_id)
        if profile is not None:
            await save_period_facts(db, appraisal, cycle, profile)
        # Everyone still in progress moves on, so nobody's goals stay open.
        appraisal.status = AppraisalStatus.SELF_REVIEW
    cycle.status = CycleStatus.REVIEWING
    await db.flush()
    await repo.cancel_suggestions(cycle.id)
    await repo.queue_summaries(cycle.id)
    return len(appraisals)


async def pass_self_due(db: AsyncSession, cycle: AppraisalCycle, today: date) -> int:
    """Move people past their self-score due date on to their manager."""
    if cycle.status is not CycleStatus.REVIEWING or today <= cycle.self_due:
        return 0
    moved = 0
    for appraisal in await AppraisalRepository(db, org_id=cycle.org_id).for_cycle(cycle.id):
        if appraisal.status is AppraisalStatus.SELF_REVIEW:
            appraisal.status = AppraisalStatus.MANAGER_REVIEW
            moved += 1
    await db.flush()
    return moved
