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

"""Suggesting a change to a confirmed goal, from either side.

The change is a proposal that names the goal it replaces; the other side
decides on it (:func:`.goal_decisions.accept_goal` swaps it in). The
employee's goes to the manager; the manager's is marked as theirs, so the
employee is the one to take or decline it, and sees it on their to-do.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_enums import GoalOrigin, GoalRevisionKind, GoalStatus
from app.models.appraisal_goal import FROM_MANAGER, AppraisalGoal
from app.repositories.appraisal_goal import AppraisalGoalRepository
from app.schemas.appraisal_goal import GoalBody, GoalEdit
from app.services.appraisals import crypto, goal_history
from app.services.appraisals.appraisal_context import AppraisalContext
from app.services.appraisals.errors import AppraisalConflictError
from app.services.appraisals.goal_history import GoalText
from app.services.appraisals.goal_rules import actions
from app.services.appraisals.goal_writes import add_goal, audit_goal, goal_rights
from app.services.appraisals.org_clock import org_today


async def _managers_change(
    db: AsyncSession, ctx: AppraisalContext, goal: AppraisalGoal, words: GoalText, reason: str
) -> AppraisalGoal:
    change = AppraisalGoal(
        id=uuid.uuid4(),
        org_id=ctx.cycle.org_id,
        profile_id=ctx.profile.id,
        cycle_id=ctx.cycle.id,
        target_period_start=ctx.cycle.period_start,
        origin=GoalOrigin.MANAGER_ADDED,
        proposed_by=ctx.caller_id,
        added_mid_period=await org_today(db, ctx.cycle.org_id) > ctx.cycle.period_start,
        status=GoalStatus.PROPOSED,
        suggestion_refs={"replaces": str(goal.id), "from": FROM_MANAGER},
    )
    crypto.seal(change, "title", words.title)
    crypto.seal(change, "measure", words.measure or None)
    db.add(change)
    goal_history.record(
        db, change, ctx.caller_id, GoalRevisionKind.CREATED, after=words, reason=reason or None
    )
    audit_goal(db, ctx, change)
    return change


async def suggest_change(
    db: AsyncSession, ctx: AppraisalContext, goal: AppraisalGoal, body: GoalEdit
) -> AppraisalGoal:
    """Propose new wording for a confirmed goal; the other side decides."""
    repo = AppraisalGoalRepository(db, org_id=ctx.cycle.org_id)
    pending = any(
        g.suggestion_refs.get("replaces") == str(goal.id) and g.status is GoalStatus.PROPOSED
        for g in await repo.for_period(ctx.profile.id, ctx.cycle.period_start)
    )
    if not actions(goal, goal_rights(ctx), pending_change=pending).suggest_change:
        raise AppraisalConflictError("A change can't be suggested for this goal now.")
    if ctx.is_self:
        change = await add_goal(
            db, ctx, GoalBody(title=body.title, measure=body.measure, reason=body.reason)
        )
        change.suggestion_refs = {"replaces": str(goal.id)}
    else:
        words = GoalText(body.title.strip(), body.measure.strip())
        change = await _managers_change(db, ctx, goal, words, body.reason.strip())
    await db.flush()
    return change
