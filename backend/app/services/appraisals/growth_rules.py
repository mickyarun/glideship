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

"""Who writes the growth conversation, and when next period's goals lock.

It opens once the result is shared and stays open after the cycle
closes: the person and their primary manager write it, everyone else
who may see the review reads it. Next period's goals lock when the
person's own review for that period opens, or that cycle closes.
"""

import uuid
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_enums import AppraisalStatus, GoalStatus
from app.models.appraisal_goal import AppraisalGoal
from app.repositories.appraisal import AppraisalRepository
from app.services.appraisals.appraisal_context import AppraisalContext
from app.services.appraisals.errors import AppraisalConflictError
from app.services.appraisals.goal_rules import MAX_GOALS, is_locked, next_position
from app.services.appraisals.goal_writes import FULL

OPEN_AT = frozenset({AppraisalStatus.SHARED, AppraisalStatus.ACKNOWLEDGED})
# Proposals don't take a slot, but there's no reason for more than this many.
MAX_LIVE = MAX_GOALS * 2


def is_open(ctx: AppraisalContext) -> bool:
    """The result has been shared."""
    return ctx.appraisal.status in OPEN_AT


def can_edit(ctx: AppraisalContext) -> bool:
    """The person or their primary manager, once it is open."""
    return is_open(ctx) and (ctx.is_self or ctx.access.is_primary_manager)


def require_edit(ctx: AppraisalContext) -> None:
    """Refuse anyone who may not write, saying why."""
    if not is_open(ctx):
        raise AppraisalConflictError("The growth conversation opens once the result is shared.")
    if not can_edit(ctx):
        raise AppraisalConflictError("Only the person and their manager write this.")


def can_remove(ctx: AppraisalContext, goal: AppraisalGoal) -> bool:
    """The manager any goal; the employee only a proposal of their own."""
    if not can_edit(ctx):
        return False
    if not ctx.is_self:
        return True
    return goal.proposed_by == ctx.caller_id and goal.status is GoalStatus.PROPOSED


def next_start(ctx: AppraisalContext) -> date:
    """The first day of the next period."""
    return ctx.cycle.period_end + timedelta(days=1)


async def open_next_cycle(db: AsyncSession, ctx: AppraisalContext) -> uuid.UUID | None:
    """Refuse once next period's goals have locked; else the next cycle to join, if open.

    Locks the person's next appraisal row first, so a review opening at the
    same moment can't let a change slip in.
    """
    require_edit(ctx)
    repo = AppraisalRepository(db, org_id=ctx.cycle.org_id)
    found = await repo.for_profile_in_period(ctx.profile.id, next_start(ctx))
    if found is None:
        return None
    appraisal, cycle = found
    await repo.lock_row(appraisal.id)
    if is_locked(appraisal, cycle):
        raise AppraisalConflictError("Next period's goals have locked: its review has opened.")
    return cycle.id


def free_position(goals: list[AppraisalGoal]) -> int:
    """The next free slot among next period's confirmed goals."""
    taken = {g.position for g in goals if g.status is GoalStatus.ACCEPTED and g.position}
    position = next_position(taken)
    if position is None:
        raise AppraisalConflictError(FULL)
    return position
