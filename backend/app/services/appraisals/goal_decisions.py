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

"""Deciding on a goal: confirming it, asking for a rewording, or declining it.

Confirming is a person's act, so it is audited. A suggestion the employee
takes up becomes their proposal for the manager to confirm, so nobody
confirms their own goal by steering the suggestions. A confirmed
suggested change takes the place of the goal it replaces.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_enums import GoalRevisionKind, GoalStatus
from app.models.appraisal_goal import AppraisalGoal
from app.models.employee_audit_event import EmployeeAuditAction
from app.repositories.appraisal_goal import AppraisalGoalRepository
from app.schemas.appraisal_goal import ReasonBody
from app.services.appraisals import audit, crypto, goal_history
from app.services.appraisals.appraisal_context import AppraisalContext
from app.services.appraisals.errors import AppraisalConflictError, AppraisalInvalidError
from app.services.appraisals.goal_history import GoalText
from app.services.appraisals.goal_rules import actions, next_position
from app.services.appraisals.goal_writes import (
    FULL,
    audit_goal,
    flush_or_full,
    goal_rights,
    taken_positions,
)


async def accept_goal(db: AsyncSession, ctx: AppraisalContext, goal: AppraisalGoal) -> None:
    """Confirm a proposal, or take up a suggestion, into a free slot."""
    if not actions(goal, goal_rights(ctx), pending_change=False).accept:
        raise AppraisalConflictError("This goal can't be confirmed now.")
    if ctx.is_self:
        goal.status, goal.proposed_by = GoalStatus.PROPOSED, ctx.caller_id
        goal_history.record(
            db,
            goal,
            ctx.caller_id,
            GoalRevisionKind.CREATED,
            reason="Picked from the suggestions.",
        )
        await db.flush()
        return
    replaces = goal.suggestion_refs.get("replaces")
    old = (
        await AppraisalGoalRepository(db, org_id=goal.org_id).get_by_id(_uuid(replaces))
        if replaces
        else None
    )
    if old is not None and old.status is GoalStatus.ACCEPTED:
        position = old.position
        old.status, old.position = GoalStatus.DISMISSED, None
        goal_history.record(
            db,
            old,
            ctx.caller_id,
            GoalRevisionKind.REMOVED,
            before=GoalText.of(old),
            reason="Replaced by the agreed change.",
        )
        await db.flush()
    else:
        position = next_position(await taken_positions(db, ctx))
    if position is None:
        raise AppraisalConflictError(FULL)
    goal.status, goal.position = GoalStatus.ACCEPTED, position
    goal.accepted_by, goal.accepted_at = ctx.caller_id, datetime.now(UTC)
    goal_history.record(db, goal, ctx.caller_id, GoalRevisionKind.CONFIRMED)
    audit.record(
        db,
        org_id=goal.org_id,
        actor_id=ctx.caller_id,
        subject_user_id=ctx.profile.user_id,
        profile_id=ctx.profile.id,
        action=EmployeeAuditAction.APPRAISAL_GOAL_ACCEPTED,
        target=goal.id,
    )
    await flush_or_full(db)


async def dismiss_goal(
    db: AsyncSession, ctx: AppraisalContext, goal: AppraisalGoal, body: ReasonBody
) -> None:
    """Decline a proposal (the manager says why), withdraw one, or drop a suggestion."""
    if not actions(goal, goal_rights(ctx), pending_change=False).dismiss:
        raise AppraisalConflictError("This goal can't be dismissed now.")
    reason = body.reason.strip() or None
    declining = goal.status is GoalStatus.PROPOSED and not ctx.is_self
    if declining and reason is None:
        raise AppraisalInvalidError("Say why you're not adding it; they'll see this.")
    goal.status = GoalStatus.DISMISSED
    crypto.seal(goal, "dismiss_reason", reason)
    kind = GoalRevisionKind.REMOVED if ctx.is_self else GoalRevisionKind.DECLINED
    goal_history.record(db, goal, ctx.caller_id, kind, reason=reason)
    if not ctx.is_self:
        audit_goal(db, ctx, goal)
    await db.flush()


async def ask_reword(
    db: AsyncSession, ctx: AppraisalContext, goal: AppraisalGoal, body: ReasonBody
) -> None:
    """Ask the employee to reword their proposal, saying what to change."""
    if not actions(goal, goal_rights(ctx), pending_change=False).ask_reword:
        raise AppraisalConflictError("Only a proposed goal can be sent back for rewording.")
    reason = body.reason.strip()
    if not reason:
        raise AppraisalInvalidError("Say what to change; they'll see this.")
    goal_history.record(db, goal, ctx.caller_id, GoalRevisionKind.REWORD_ASKED, reason=reason)
    await db.flush()


def _uuid(value: object) -> uuid.UUID:
    return uuid.UUID(str(value))
