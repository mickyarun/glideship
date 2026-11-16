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

"""Adding, rewording and removing goals, with a history line for each."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_enums import GoalOrigin, GoalRevisionKind, GoalStatus, SuggestionBasis
from app.models.appraisal_goal import AppraisalGoal
from app.models.employee_audit_event import EmployeeAuditAction
from app.repositories.appraisal_goal import AppraisalGoalRepository
from app.schemas.appraisal_goal import GoalBody, GoalEdit
from app.services.appraisals import audit, crypto, goal_history
from app.services.appraisals.appraisal_context import AppraisalContext
from app.services.appraisals.errors import AppraisalConflictError, AppraisalInvalidError
from app.services.appraisals.goal_history import GoalText
from app.services.appraisals.goal_rules import GoalRights, actions, is_locked, next_position
from app.services.appraisals.org_clock import org_today

FULL = "This period already has three confirmed goals. Remove or change one first."
TAKEN = "Someone just confirmed a goal into that slot. Reload and try again."


def goal_rights(ctx: AppraisalContext) -> GoalRights:
    """The caller's rights over this period's goals, nothing once they lock."""
    if is_locked(ctx.appraisal, ctx.cycle):
        return GoalRights(employee=False, manager=False)
    return GoalRights(
        employee=ctx.is_self and ctx.access.edit_check_ins, manager=ctx.access.manage_goals
    )


async def taken_positions(db: AsyncSession, ctx: AppraisalContext) -> set[int]:
    """Slots used by this period's confirmed goals."""
    accepted = await AppraisalGoalRepository(db, org_id=ctx.cycle.org_id).accepted_for_period(
        ctx.profile.id, ctx.cycle.period_start
    )
    return {g.position for g in accepted if g.position is not None}


async def flush_or_full(db: AsyncSession) -> None:
    """Flush; two confirmations racing for one slot lose one to the index."""
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError as exc:
        raise AppraisalConflictError(TAKEN) from exc


def audit_goal(db: AsyncSession, ctx: AppraisalContext, goal: AppraisalGoal) -> None:
    """Log a manager's change to someone's goal (ids only)."""
    audit.record(
        db,
        org_id=goal.org_id,
        actor_id=ctx.caller_id,
        subject_user_id=ctx.profile.user_id,
        profile_id=ctx.profile.id,
        action=EmployeeAuditAction.APPRAISAL_GOAL_CHANGED,
        target=goal.id,
    )


async def add_goal(db: AsyncSession, ctx: AppraisalContext, body: GoalBody) -> AppraisalGoal:
    """The employee proposes a goal; the manager adds a confirmed one with a reason."""
    rights = goal_rights(ctx)
    if not (rights.employee or rights.manager):
        raise AppraisalConflictError("Goals can't be added now.")
    words = GoalText(body.title.strip(), body.measure.strip())
    reason = body.reason.strip() or None
    as_manager = rights.manager and not ctx.is_self
    library = body.source == "role_library"
    goal = AppraisalGoal(
        id=uuid.uuid4(),
        org_id=ctx.cycle.org_id,
        profile_id=ctx.profile.id,
        cycle_id=ctx.cycle.id,
        target_period_start=ctx.cycle.period_start,
        # A manager's goal is theirs (and theirs to remove), wherever its
        # words came from; the library is kept as its basis.
        origin=GoalOrigin.MANAGER_ADDED
        if as_manager
        else GoalOrigin.ROLE_LIBRARY
        if library
        else GoalOrigin.EMPLOYEE_OWN,
        suggestion_basis=SuggestionBasis.ROLE_LIBRARY if library else None,
        proposed_by=ctx.caller_id,
        added_mid_period=await org_today(db, ctx.cycle.org_id) > ctx.cycle.period_start,
        status=GoalStatus.PROPOSED,
        suggestion_refs={},
    )
    if as_manager:
        if reason is None:
            raise AppraisalInvalidError("Say why this goal matters now; they'll see it.")
        position = next_position(await taken_positions(db, ctx))
        if position is None:
            raise AppraisalConflictError(FULL)
        goal.status, goal.position = GoalStatus.ACCEPTED, position
        goal.accepted_by, goal.accepted_at = ctx.caller_id, datetime.now(UTC)
    crypto.seal(goal, "title", words.title)
    crypto.seal(goal, "measure", words.measure or None)
    db.add(goal)
    goal_history.record(
        db, goal, ctx.caller_id, GoalRevisionKind.CREATED, after=words, reason=reason
    )
    await flush_or_full(db)
    return goal


async def edit_goal(
    db: AsyncSession, ctx: AppraisalContext, goal: AppraisalGoal, body: GoalEdit
) -> None:
    """Reword a goal; a manager changing a confirmed one must give a reason."""
    if not actions(goal, goal_rights(ctx), pending_change=False).edit:
        raise AppraisalConflictError("This goal can't be changed now.")
    reason = body.reason.strip() or None
    as_manager = not ctx.is_self
    if as_manager and reason is None:
        raise AppraisalInvalidError("Say why the goal changed; they'll see it.")
    before, after = GoalText.of(goal), GoalText(body.title.strip(), body.measure.strip())
    if before == after:
        return
    if goal.status is GoalStatus.SUGGESTED and goal.original is None:
        crypto.seal_json(goal, "original", before.as_json())
    crypto.seal(goal, "title", after.title)
    crypto.seal(goal, "measure", after.measure or None)
    goal_history.record(
        db, goal, ctx.caller_id, GoalRevisionKind.EDITED, before=before, after=after, reason=reason
    )
    if as_manager:
        audit_goal(db, ctx, goal)
    await db.flush()


async def remove_goal(db: AsyncSession, ctx: AppraisalContext, goal: AppraisalGoal) -> None:
    """The manager takes back a goal they added, before the review opens."""
    if not actions(goal, goal_rights(ctx), pending_change=False).remove:
        raise AppraisalConflictError("Only a goal you added can be removed, before the review.")
    goal.status, goal.position = GoalStatus.DISMISSED, None
    goal_history.record(
        db, goal, ctx.caller_id, GoalRevisionKind.REMOVED, before=GoalText.of(goal)
    )
    await db.flush()


async def suggest_change(
    db: AsyncSession, ctx: AppraisalContext, goal: AppraisalGoal, body: GoalEdit
) -> AppraisalGoal:
    """The employee proposes new wording for a confirmed goal; the manager decides."""
    repo = AppraisalGoalRepository(db, org_id=ctx.cycle.org_id)
    pending = any(
        g.suggestion_refs.get("replaces") == str(goal.id) and g.status is GoalStatus.PROPOSED
        for g in await repo.for_period(ctx.profile.id, ctx.cycle.period_start)
    )
    if not actions(goal, goal_rights(ctx), pending_change=pending).suggest_change:
        raise AppraisalConflictError("A change can't be suggested for this goal now.")
    change = await add_goal(
        db, ctx, GoalBody(title=body.title, measure=body.measure, reason=body.reason)
    )
    change.suggestion_refs = {"replaces": str(goal.id)}
    await db.flush()
    return change
