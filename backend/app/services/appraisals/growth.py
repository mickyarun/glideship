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
first day: they join its cycle at once if it is already running, or
when it opens. The manager confirms what the employee proposes, as
for any goal, and a goal can be taken back until it locks.
"""

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_enums import AppraisalStatus, GoalOrigin, GoalRevisionKind, GoalStatus
from app.models.appraisal_goal import AppraisalGoal
from app.repositories.appraisal import AppraisalRepository
from app.repositories.appraisal_cycle import AppraisalCycleRepository
from app.repositories.appraisal_goal import AppraisalGoalRepository
from app.repositories.user import UserRepository
from app.schemas.appraisal_goal import GoalBody
from app.schemas.appraisal_growth import GrowthBody, GrowthRead, NextGoal
from app.services.appraisals import crypto, goal_history
from app.services.appraisals.appraisal_context import AppraisalContext
from app.services.appraisals.errors import AppraisalConflictError, AppraisalNotFoundError
from app.services.appraisals.goal_history import GoalText
from app.services.appraisals.goal_rules import MAX_GOALS, next_position
from app.services.appraisals.goal_writes import FULL, audit_goal, flush_or_full

OPEN_AT = frozenset({AppraisalStatus.SHARED, AppraisalStatus.ACKNOWLEDGED})


def is_open(ctx: AppraisalContext) -> bool:
    """The result has been shared."""
    return ctx.appraisal.status in OPEN_AT


def can_edit(ctx: AppraisalContext) -> bool:
    """The person or their acting primary manager, once it is open."""
    return is_open(ctx) and (
        (ctx.is_self and ctx.access.edit_check_ins) or ctx.access.manage_goals
    )


def next_start(ctx: AppraisalContext) -> date:
    """The first day of the next period."""
    return ctx.cycle.period_end + timedelta(days=1)


async def _goals(db: AsyncSession, ctx: AppraisalContext) -> list[AppraisalGoal]:
    goals = await AppraisalGoalRepository(db, org_id=ctx.cycle.org_id).for_period(
        ctx.profile.id, next_start(ctx)
    )
    return [g for g in goals if g.status in (GoalStatus.ACCEPTED, GoalStatus.PROPOSED)]


async def read_growth(db: AsyncSession, ctx: AppraisalContext) -> GrowthRead:
    """The conversation for this viewer."""
    goals = await _goals(db, ctx) if is_open(ctx) else []
    people = {g.proposed_by for g in goals if g.proposed_by}
    names = {u.id: u.name for u in await UserRepository(db).get_many_by_ids(list(people))}
    editable, manager = can_edit(ctx), can_edit(ctx) and not ctx.is_self
    return GrowthRead(
        open=is_open(ctx),
        can_edit=editable,
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
                can_remove=editable and (manager or g.proposed_by == ctx.caller_id),
            )
            for g in goals
        ],
    )


async def save_growth(db: AsyncSession, ctx: AppraisalContext, body: GrowthBody) -> None:
    """Store the strength and the focus."""
    if not can_edit(ctx):
        raise AppraisalConflictError("The growth conversation opens once the result is shared.")
    crypto.seal(ctx.appraisal, "growth_strength", body.strength.strip())
    crypto.seal(ctx.appraisal, "growth_focus", body.focus.strip())
    await db.flush()


async def _check_goals_open(db: AsyncSession, ctx: AppraisalContext) -> None:
    """Refuse once the next period's own review has opened: its goals are locked."""
    if not can_edit(ctx):
        raise AppraisalConflictError("The growth conversation opens once the result is shared.")
    cycle = await AppraisalCycleRepository(db, org_id=ctx.cycle.org_id).opened_for_period(
        next_start(ctx)
    )
    if cycle is None:
        return
    nxt = await AppraisalRepository(db, org_id=ctx.cycle.org_id).for_profile_in_cycle(
        ctx.profile.id, cycle.id
    )
    if nxt is not None and nxt.status is not AppraisalStatus.ENROLLED:
        raise AppraisalConflictError("Next period's goals have locked: its review has opened.")


async def _position(db: AsyncSession, ctx: AppraisalContext) -> int:
    accepted = [g for g in await _goals(db, ctx) if g.status is GoalStatus.ACCEPTED]
    position = next_position({g.position for g in accepted if g.position is not None})
    if position is None:
        raise AppraisalConflictError(FULL)
    return position


async def add_next_goal(db: AsyncSession, ctx: AppraisalContext, body: GoalBody) -> None:
    """The manager adds a confirmed goal; the employee proposes one."""
    await _check_goals_open(db, ctx)
    as_manager = not ctx.is_self
    start = next_start(ctx)
    cycle = await AppraisalCycleRepository(db, org_id=ctx.cycle.org_id).opened_for_period(start)
    goal = AppraisalGoal(
        id=uuid.uuid4(),
        org_id=ctx.cycle.org_id,
        profile_id=ctx.profile.id,
        cycle_id=cycle.id if cycle else None,
        target_period_start=start,
        origin=GoalOrigin.MANAGER_ADDED if as_manager else GoalOrigin.EMPLOYEE_OWN,
        proposed_by=ctx.caller_id,
        added_mid_period=False,
        status=GoalStatus.PROPOSED,
        suggestion_refs={},
    )
    if as_manager:
        goal.status, goal.position = GoalStatus.ACCEPTED, await _position(db, ctx)
        goal.accepted_by, goal.accepted_at = ctx.caller_id, datetime.now(UTC)
    words = GoalText(body.title.strip(), body.measure.strip())
    crypto.seal(goal, "title", words.title)
    crypto.seal(goal, "measure", words.measure or None)
    db.add(goal)
    reason = body.reason.strip() or "Agreed in the growth conversation."
    goal_history.record(
        db, goal, ctx.caller_id, GoalRevisionKind.CREATED, after=words, reason=reason
    )
    await flush_or_full(db)


async def _goal(db: AsyncSession, ctx: AppraisalContext, goal_id: uuid.UUID) -> AppraisalGoal:
    goal = next((g for g in await _goals(db, ctx) if g.id == goal_id), None)
    if goal is None:
        raise AppraisalNotFoundError("Goal not found.")
    return goal


async def accept_next_goal(db: AsyncSession, ctx: AppraisalContext, goal_id: uuid.UUID) -> None:
    """The manager confirms a goal the employee proposed."""
    await _check_goals_open(db, ctx)
    goal = await _goal(db, ctx, goal_id)
    if not (not ctx.is_self and goal.status is GoalStatus.PROPOSED):
        raise AppraisalConflictError("Only the manager confirms a proposed goal.")
    goal.status, goal.position = GoalStatus.ACCEPTED, await _position(db, ctx)
    goal.accepted_by, goal.accepted_at = ctx.caller_id, datetime.now(UTC)
    goal_history.record(db, goal, ctx.caller_id, GoalRevisionKind.CONFIRMED)
    audit_goal(db, ctx, goal)
    await flush_or_full(db)


async def remove_next_goal(db: AsyncSession, ctx: AppraisalContext, goal_id: uuid.UUID) -> None:
    """Take a goal back: the manager any, the employee their own proposal."""
    await _check_goals_open(db, ctx)
    goal = await _goal(db, ctx, goal_id)
    own = goal.proposed_by == ctx.caller_id
    if ctx.is_self and not own:
        raise AppraisalConflictError("This goal can't be taken back now.")
    goal.status, goal.position = GoalStatus.DISMISSED, None
    goal_history.record(
        db, goal, ctx.caller_id, GoalRevisionKind.REMOVED, before=GoalText.of(goal)
    )
    await db.flush()
