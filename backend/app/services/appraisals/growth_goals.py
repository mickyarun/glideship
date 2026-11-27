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

"""Deciding on next period's goals in the growth conversation.

The manager confirms or rejects what the employee proposes, saying why
if they like; the employee sees a rejection and its reason. Either side
may take back what they may remove. Each change is kept in the goal's
history, and a manager's is audited (ids only).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_enums import GoalRevisionKind, GoalStatus
from app.models.appraisal_goal import AppraisalGoal
from app.repositories.appraisal_goal import AppraisalGoalRepository
from app.schemas.appraisal_goal import ReasonBody
from app.services.appraisals import crypto, goal_history
from app.services.appraisals.appraisal_context import AppraisalContext
from app.services.appraisals.errors import AppraisalConflictError, AppraisalNotFoundError
from app.services.appraisals.goal_history import GoalText
from app.services.appraisals.goal_rules import is_rejected, sees_rejections
from app.services.appraisals.goal_writes import audit_goal, flush_or_full
from app.services.appraisals.growth_rules import (
    can_reject,
    can_remove,
    free_position,
    next_start,
    open_next_cycle,
)
from app.services.appraisals.settings import goal_limit

LIVE = (GoalStatus.ACCEPTED, GoalStatus.PROPOSED)


async def next_goals(
    db: AsyncSession, ctx: AppraisalContext
) -> tuple[list[AppraisalGoal], list[AppraisalGoal]]:
    """Next period's live goals, and the person's proposals the manager rejected."""
    repo = AppraisalGoalRepository(db, org_id=ctx.cycle.org_id)
    goals = await repo.for_period(ctx.profile.id, next_start(ctx))
    live = [g for g in goals if g.status in LIVE]
    if not sees_rejections(ctx.is_self, ctx.access.is_primary_manager):
        return live, []
    dropped = [g for g in goals if g.status is GoalStatus.DISMISSED]
    kinds: dict[uuid.UUID, list[GoalRevisionKind]] = {g.id: [] for g in dropped}
    for revision in await repo.revisions(list(kinds)):
        kinds[revision.goal_id].append(revision.kind)
    rejected = [g for g in dropped if is_rejected(g, ctx.profile.user_id, kinds[g.id])]
    return live, rejected


async def live_goals(db: AsyncSession, ctx: AppraisalContext) -> list[AppraisalGoal]:
    """Next period's confirmed and proposed goals."""
    goals = await AppraisalGoalRepository(db, org_id=ctx.cycle.org_id).for_period(
        ctx.profile.id, next_start(ctx)
    )
    return [g for g in goals if g.status in LIVE]


async def _goal(db: AsyncSession, ctx: AppraisalContext, goal_id: uuid.UUID) -> AppraisalGoal:
    goal = next((g for g in await live_goals(db, ctx) if g.id == goal_id), None)
    if goal is None:
        raise AppraisalNotFoundError("Goal not found.")
    return goal


async def accept_next_goal(db: AsyncSession, ctx: AppraisalContext, goal_id: uuid.UUID) -> None:
    """The manager confirms a goal the employee proposed."""
    await open_next_cycle(db, ctx)
    goal = await _goal(db, ctx, goal_id)
    if ctx.is_self or goal.status is not GoalStatus.PROPOSED:
        raise AppraisalConflictError("Only the manager confirms a proposed goal.")
    limit = await goal_limit(db, ctx.cycle.org_id)
    position = free_position(await live_goals(db, ctx), limit)
    goal.status, goal.position = GoalStatus.ACCEPTED, position
    goal.accepted_by, goal.accepted_at = ctx.caller_id, datetime.now(UTC)
    goal_history.record(db, goal, ctx.caller_id, GoalRevisionKind.CONFIRMED)
    audit_goal(db, ctx, goal)
    await flush_or_full(db)


async def reject_next_goal(
    db: AsyncSession, ctx: AppraisalContext, goal_id: uuid.UUID, body: ReasonBody
) -> None:
    """The manager rejects a goal the employee proposed; the reason is optional."""
    await open_next_cycle(db, ctx)
    goal = await _goal(db, ctx, goal_id)
    if not can_reject(ctx, goal):
        raise AppraisalConflictError("This goal can't be rejected now.")
    reason = body.reason.strip() or None
    goal.status = GoalStatus.DISMISSED
    crypto.seal(goal, "dismiss_reason", reason)
    goal_history.record(db, goal, ctx.caller_id, GoalRevisionKind.DECLINED, reason=reason)
    audit_goal(db, ctx, goal)
    await db.flush()


async def remove_next_goal(db: AsyncSession, ctx: AppraisalContext, goal_id: uuid.UUID) -> None:
    """Take a goal back: the manager a confirmed one, the employee their own proposal."""
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
