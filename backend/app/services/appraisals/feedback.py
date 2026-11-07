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

"""Loading and writing one manager feedback item.

The primary manager writes it while the cycle runs; the item must also be
theirs, so a finished item stays with the manager who wrote it after the
reporting line changes. The employee sees what is saved straight away.
Marking it done needs both lines; goal statuses are optional and only
quarterly items have them. The person sees the item once anything is saved.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal import Appraisal
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import CheckInCadence, FeedbackStatus
from app.models.appraisal_manager_feedback import AppraisalManagerFeedback
from app.models.employee_audit_event import EmployeeAuditAction
from app.models.employee_profile import EmployeeProfile
from app.repositories.appraisal import AppraisalRepository
from app.repositories.appraisal_cycle import AppraisalCycleRepository
from app.repositories.appraisal_feedback import AppraisalFeedbackRepository
from app.repositories.appraisal_goal import AppraisalGoalRepository
from app.repositories.employee_profile import EmployeeProfileRepository
from app.schemas.appraisal_feedback import FeedbackBody
from app.services.appraisals import audit, crypto
from app.services.appraisals.access import AppraisalAccess
from app.services.appraisals.context import Caller, rights_over, stage_for
from app.services.appraisals.errors import (
    AppraisalConflictError,
    AppraisalInvalidError,
    AppraisalNotFoundError,
)

NOT_FOUND = "Feedback not found."


@dataclass(frozen=True)
class FeedbackContext:
    """A feedback item with what is needed to show or change it."""

    item: AppraisalManagerFeedback
    profile: EmployeeProfile
    appraisal: Appraisal | None
    cycle: AppraisalCycle | None
    access: AppraisalAccess
    caller_id: uuid.UUID

    @property
    def can_edit(self) -> bool:
        """The acting primary manager, on their own item."""
        return self.access.write_feedback and self.item.manager_user_id == self.caller_id

    @property
    def written(self) -> bool:
        """Something is saved, so the employee sees it."""
        return written(self.item)


def written(item: AppraisalManagerFeedback) -> bool:
    """A line or a goal status is saved: the employee sees the item from then on."""
    return item.keep_note is not None or item.try_note is not None or bool(item.goal_status)


async def feedback_context(
    db: AsyncSession, caller: Caller, feedback_id: uuid.UUID
) -> FeedbackContext:
    """Load an item the caller may see; "not found" otherwise.

    The employee only sees an item once the manager has written something.
    """
    item = await AppraisalFeedbackRepository(db, org_id=caller.org_id).get_by_id(feedback_id)
    if item is None:
        raise AppraisalNotFoundError(NOT_FOUND)
    profile = await EmployeeProfileRepository(db, org_id=caller.org_id).get_by_id(item.profile_id)
    if profile is None:
        raise AppraisalNotFoundError(NOT_FOUND)
    appraisal = await AppraisalRepository(db, org_id=caller.org_id).for_profile_in_cycle(
        profile.id, item.cycle_id
    )
    cycle = await AppraisalCycleRepository(db, org_id=caller.org_id).get_by_id(item.cycle_id)
    access = await rights_over(db, caller, profile, appraisal, stage_for(appraisal, cycle))
    ctx = FeedbackContext(item, profile, appraisal, cycle, access, caller.user_id)
    hidden = caller.user_id == profile.user_id and not ctx.written
    if not access.view_feedback or hidden:
        raise AppraisalNotFoundError(NOT_FOUND)
    return ctx


async def _goal_checks(
    db: AsyncSession, ctx: FeedbackContext, body: FeedbackBody
) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    """The statuses and notes to store, checked against this period's goals."""
    item = ctx.item
    if item.cadence is not CheckInCadence.QUARTERLY or ctx.cycle is None:
        raise AppraisalInvalidError("Goal statuses are only part of quarterly feedback.")
    accepted = await AppraisalGoalRepository(db, org_id=item.org_id).accepted_for_period(
        ctx.profile.id, ctx.cycle.period_start
    )
    known = {g.id for g in accepted}
    goals: dict[str, dict[str, str]] = {}
    notes: dict[str, str] = {}
    for goal in body.goals or []:
        if goal.goal_id not in known:
            raise AppraisalInvalidError("That goal isn't one of this period's goals.")
        goals[str(goal.goal_id)] = {"status": goal.status.value}
        if goal.note.strip():
            notes[str(goal.goal_id)] = goal.note.strip()
    return goals, notes


async def save_feedback(
    db: AsyncSession, caller: Caller, ctx: FeedbackContext, body: FeedbackBody
) -> None:
    """Store the lines and, when sent, the goal statuses; an empty line clears it.

    Changing what the person may already have read is audited, ids only.
    """
    if not ctx.can_edit:
        raise AppraisalConflictError("Only the person's manager can write this feedback now.")
    item = ctx.item
    seen = written(item)
    before = (crypto.unseal(item, "keep_note"), crypto.unseal(item, "try_note"), item.goal_status)
    keep, try_next = body.keep.strip(), body.try_next.strip()
    crypto.seal(item, "keep_note", keep)
    crypto.seal(item, "try_note", try_next)
    if body.goals is not None:
        goals, notes = await _goal_checks(db, ctx, body) if body.goals else ({}, {})
        item.goal_status = goals
        crypto.seal_json(item, "goal_notes", notes or None)
    if item.status is FeedbackStatus.DONE and not (keep and try_next):
        # Done means both lines are there; clearing one reopens it.
        item.status, item.done_at = FeedbackStatus.OPEN, None
    after = (keep or None, try_next or None, item.goal_status)
    if seen and before != after:
        _audit(db, caller, ctx, EmployeeAuditAction.APPRAISAL_CHANGED)
    await db.flush()


def _audit(
    db: AsyncSession, caller: Caller, ctx: FeedbackContext, action: EmployeeAuditAction
) -> None:
    audit.record(
        db,
        org_id=caller.org_id,
        actor_id=caller.user_id,
        subject_user_id=ctx.profile.user_id,
        profile_id=ctx.profile.id,
        action=action,
        target=ctx.item.id,
    )


async def mark_done(db: AsyncSession, caller: Caller, ctx: FeedbackContext) -> None:
    """Mark the item done once both lines are written."""
    if not ctx.can_edit:
        raise AppraisalConflictError("Only the person's manager can finish this feedback now.")
    item = ctx.item
    if not (crypto.unseal(item, "keep_note") and crypto.unseal(item, "try_note")):
        raise AppraisalInvalidError("Write what to keep doing and what to try next first.")
    if item.status is FeedbackStatus.DONE:
        return
    item.status, item.done_at = FeedbackStatus.DONE, datetime.now(UTC)
    _audit(db, caller, ctx, EmployeeAuditAction.APPRAISAL_FEEDBACK_GIVEN)
    await db.flush()
