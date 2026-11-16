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

"""The growth conversation, opened once a result is shared.

The person and their primary manager agree one strength to use more,
one thing to work on, and two or three goals for the next period. No
band is part of it. Next period's goals are kept against that period's
first day: they join the person's own next cycle at once if it is
already running, or when it enrols them. The manager confirms what the
employee proposes, as for any goal; the rules are in :mod:`.growth_rules`.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_enums import GoalOrigin, GoalRevisionKind, GoalStatus
from app.models.appraisal_goal import AppraisalGoal
from app.models.employee_audit_event import EmployeeAuditAction
from app.repositories.appraisal_goal import AppraisalGoalRepository
from app.repositories.user import UserRepository
from app.schemas.appraisal_goal import GoalBody
from app.schemas.appraisal_growth import GrowthBody, GrowthRead, NextGoal
from app.services.appraisals import audit, crypto, goal_history
from app.services.appraisals.appraisal_context import AppraisalContext
from app.services.appraisals.errors import AppraisalConflictError, AppraisalNotFoundError
from app.services.appraisals.goal_history import GoalText
from app.services.appraisals.goal_rules import MAX_GOALS
from app.services.appraisals.goal_writes import audit_goal, flush_or_full
from app.services.appraisals.growth_rules import (
    MAX_LIVE,
    can_edit,
    can_remove,
    free_position,
    is_open,
    next_start,
    open_next_cycle,
    require_edit,
)

LIVE = (GoalStatus.ACCEPTED, GoalStatus.PROPOSED)


async def _goals(db: AsyncSession, ctx: AppraisalContext) -> list[AppraisalGoal]:
    goals = await AppraisalGoalRepository(db, org_id=ctx.cycle.org_id).for_period(
        ctx.profile.id, next_start(ctx)
    )
    return [g for g in goals if g.status in LIVE]


async def read_growth(db: AsyncSession, ctx: AppraisalContext) -> GrowthRead:
    """The conversation for this viewer."""
    goals = await _goals(db, ctx) if is_open(ctx) else []
    people = {g.proposed_by for g in goals if g.proposed_by}
    names = {u.id: u.name for u in await UserRepository(db).get_many_by_ids(list(people))}
    manager = can_edit(ctx) and not ctx.is_self
    return GrowthRead(
        open=is_open(ctx),
        can_edit=can_edit(ctx),
        is_self=ctx.is_self,
        strength=crypto.unseal(ctx.appraisal, "growth_strength") or "",
        focus=crypto.unseal(ctx.appraisal, "growth_focus") or "",
        next_period_start=next_start(ctx),
        limit=MAX_GOALS,
        goals=[
            NextGoal(
                id=g.id,
                title=crypto.unseal(g, "title") or "",
                measure=crypto.unseal(g, "measure") or "",
                status=g.status,
                origin=g.origin,
                proposed_by_name=names.get(g.proposed_by, "") if g.proposed_by else "",
                can_accept=manager and g.status is GoalStatus.PROPOSED,
                can_remove=can_remove(ctx, g),
            )
            for g in goals
        ],
    )


async def save_growth(db: AsyncSession, ctx: AppraisalContext, body: GrowthBody) -> None:
    """Store the strength and the focus; a change is audited (ids only)."""
    require_edit(ctx)
    appraisal = ctx.appraisal
    before = (
        crypto.unseal(appraisal, "growth_strength"),
        crypto.unseal(appraisal, "growth_focus"),
    )
    strength, focus = body.strength.strip(), body.focus.strip()
    crypto.seal(appraisal, "growth_strength", strength)
    crypto.seal(appraisal, "growth_focus", focus)
    if before != (strength or None, focus or None):
        audit.record(
            db,
            org_id=appraisal.org_id,
            actor_id=ctx.caller_id,
            subject_user_id=ctx.profile.user_id,
            profile_id=ctx.profile.id,
            action=EmployeeAuditAction.APPRAISAL_CHANGED,
            target=appraisal.id,
        )
    await db.flush()


async def add_next_goal(db: AsyncSession, ctx: AppraisalContext, body: GoalBody) -> None:
    """The manager adds a confirmed goal; the employee proposes one."""
    cycle_id = await open_next_cycle(db, ctx)
    goals = await _goals(db, ctx)
    if len(goals) >= MAX_LIVE:
        raise AppraisalConflictError("That's plenty of goals for one period.")
    as_manager = not ctx.is_self
    goal = AppraisalGoal(
        id=uuid.uuid4(),
        org_id=ctx.cycle.org_id,
        profile_id=ctx.profile.id,
        cycle_id=cycle_id,
        target_period_start=next_start(ctx),
        origin=GoalOrigin.MANAGER_ADDED if as_manager else GoalOrigin.EMPLOYEE_OWN,
        proposed_by=ctx.caller_id,
        added_mid_period=False,
        status=GoalStatus.PROPOSED,
        suggestion_refs={},
    )
    if as_manager:
        goal.status, goal.position = GoalStatus.ACCEPTED, free_position(goals)
        goal.accepted_by, goal.accepted_at = ctx.caller_id, datetime.now(UTC)
    words = GoalText(body.title.strip(), body.measure.strip())
    crypto.seal(goal, "title", words.title)
    crypto.seal(goal, "measure", words.measure or None)
    db.add(goal)
    reason = body.reason.strip() or "Agreed in the growth conversation."
    goal_history.record(
        db, goal, ctx.caller_id, GoalRevisionKind.CREATED, after=words, reason=reason
    )
    if as_manager:
        audit_goal(db, ctx, goal)
    await flush_or_full(db)


async def _goal(db: AsyncSession, ctx: AppraisalContext, goal_id: uuid.UUID) -> AppraisalGoal:
    goal = next((g for g in await _goals(db, ctx) if g.id == goal_id), None)
    if goal is None:
        raise AppraisalNotFoundError("Goal not found.")
    return goal


async def accept_next_goal(db: AsyncSession, ctx: AppraisalContext, goal_id: uuid.UUID) -> None:
    """The manager confirms a goal the employee proposed."""
    await open_next_cycle(db, ctx)
    goal = await _goal(db, ctx, goal_id)
    if ctx.is_self or goal.status is not GoalStatus.PROPOSED:
        raise AppraisalConflictError("Only the manager confirms a proposed goal.")
    goal.status, goal.position = GoalStatus.ACCEPTED, free_position(await _goals(db, ctx))
    goal.accepted_by, goal.accepted_at = ctx.caller_id, datetime.now(UTC)
    goal_history.record(db, goal, ctx.caller_id, GoalRevisionKind.CONFIRMED)
    audit_goal(db, ctx, goal)
    await flush_or_full(db)


async def remove_next_goal(db: AsyncSession, ctx: AppraisalContext, goal_id: uuid.UUID) -> None:
    """Take a goal back: the manager any, the employee only their own proposal."""
    await open_next_cycle(db, ctx)
    goal = await _goal(db, ctx, goal_id)
    if not can_remove(ctx, goal):
        raise AppraisalConflictError("This goal can't be taken back now.")
    before = GoalText.of(goal)
    goal.status, goal.position = GoalStatus.DISMISSED, None
    goal_history.record(db, goal, ctx.caller_id, GoalRevisionKind.REMOVED, before=before)
    if not ctx.is_self:
        audit_goal(db, ctx, goal)
    await db.flush()
