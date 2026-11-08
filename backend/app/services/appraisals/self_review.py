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

"""The employee's self-review: a result and reason per goal, and an overall band.

Saved as they go; submitting checks the rules in :mod:`.review_rules` and
passes the review to the manager. Evidence comes only from the period.
"""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_enums import AppraisalStatus
from app.models.appraisal_goal import AppraisalGoal
from app.repositories.appraisal_goal import AppraisalGoalRepository
from app.schemas.appraisal_review import SelfBody
from app.services.appraisals import crypto
from app.services.appraisals.appraisal_context import AppraisalContext
from app.services.appraisals.errors import AppraisalConflictError, AppraisalInvalidError
from app.services.appraisals.evidence import evidence_pool, pick
from app.services.appraisals.review_rules import self_problem


async def period_goals(db: AsyncSession, ctx: AppraisalContext) -> dict[str, AppraisalGoal]:
    """The period's confirmed goals, by id."""
    goals = await AppraisalGoalRepository(db, org_id=ctx.cycle.org_id).accepted_for_period(
        ctx.profile.id, ctx.cycle.period_start
    )
    return {str(g.id): g for g in goals}


async def save_self(db: AsyncSession, ctx: AppraisalContext, body: SelfBody) -> None:
    """Store the self-review as it stands."""
    appraisal = ctx.appraisal
    if not (ctx.access.edit_self_score and appraisal.status is AppraisalStatus.SELF_REVIEW):
        raise AppraisalConflictError("The self-review isn't open for changes.")
    pool = await evidence_pool(db, appraisal)
    goals = await period_goals(db, ctx)
    for item in body.goals:
        goal = goals.get(str(item.goal_id))
        if goal is None:
            raise AppraisalInvalidError("That goal isn't one of this period's goals.")
        goal.self_result = item.result
        crypto.seal(goal, "self_reason", item.reason.strip())
        goal.self_evidence = pick(pool, item.evidence)
    appraisal.self_band = body.band
    crypto.seal(appraisal, "self_reason", body.reason.strip())
    appraisal.self_evidence = pick(pool, body.evidence)
    await db.flush()


async def submit_self(db: AsyncSession, ctx: AppraisalContext) -> None:
    """Hand the self-review to the manager once it meets the rules."""
    appraisal = ctx.appraisal
    if not (ctx.access.edit_self_score and appraisal.status is AppraisalStatus.SELF_REVIEW):
        raise AppraisalConflictError("The self-review isn't open for changes.")
    goals = await period_goals(db, ctx)
    problem = self_problem(
        appraisal.self_band,
        len(appraisal.self_evidence or []),
        {key: goal.self_result for key, goal in goals.items()},
    )
    if problem:
        raise AppraisalInvalidError(problem)
    appraisal.self_submitted_at = datetime.now(UTC)
    appraisal.status = AppraisalStatus.MANAGER_REVIEW
    await db.flush()
