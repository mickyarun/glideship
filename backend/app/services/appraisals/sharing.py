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

"""After the manager submits: HR sends back or shares; the employee acknowledges.

Each step is audited, and locks the row first so two can't cross. Sharing
in bulk shares every review in calibration the HR person may act on.
"""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import AppraisalStatus, CycleStatus
from app.models.employee_audit_event import EmployeeAuditAction
from app.repositories.appraisal import AppraisalRepository
from app.repositories.appraisal_goal import AppraisalGoalRepository
from app.services.appraisals import audit, crypto
from app.services.appraisals.appraisal_context import AppraisalContext
from app.services.appraisals.calibration import visible_appraisals
from app.services.appraisals.context import Caller
from app.services.appraisals.errors import AppraisalConflictError


def _audit(db: AsyncSession, ctx: AppraisalContext, action: EmployeeAuditAction) -> None:
    audit.record(
        db,
        org_id=ctx.appraisal.org_id,
        actor_id=ctx.caller_id,
        subject_user_id=ctx.profile.user_id,
        profile_id=ctx.profile.id,
        action=action,
        target=ctx.appraisal.id,
    )


async def _lock(db: AsyncSession, ctx: AppraisalContext) -> None:
    await AppraisalRepository(db, org_id=ctx.appraisal.org_id).lock_row(ctx.appraisal.id)


async def send_back(db: AsyncSession, ctx: AppraisalContext, note: str) -> None:
    """Return the review to the manager with a note they read; the results reopen."""
    await _lock(db, ctx)
    appraisal = ctx.appraisal
    if not (ctx.access.send_back and appraisal.status is AppraisalStatus.CALIBRATION):
        raise AppraisalConflictError("Only a review waiting for HR can be sent back.")
    appraisal.status = AppraisalStatus.MANAGER_REVIEW
    appraisal.manager_submitted_at = None
    appraisal.final_band = None
    appraisal.review_notified_at = None
    for goal in await AppraisalGoalRepository(db, org_id=appraisal.org_id).accepted_for_period(
        ctx.profile.id, ctx.cycle.period_start
    ):
        goal.final_result = None
    crypto.seal(appraisal, "send_back_note", note.strip())
    _audit(db, ctx, EmployeeAuditAction.APPRAISAL_SENT_BACK)
    await db.flush()


async def share(db: AsyncSession, ctx: AppraisalContext) -> None:
    """Show the result to the employee."""
    await _lock(db, ctx)
    appraisal = ctx.appraisal
    if not (ctx.access.share and appraisal.status is AppraisalStatus.CALIBRATION):
        raise AppraisalConflictError("Only a review waiting for HR can be shared.")
    appraisal.status = AppraisalStatus.SHARED
    appraisal.shared_at = datetime.now(UTC)
    _audit(db, ctx, EmployeeAuditAction.APPRAISAL_SHARED)
    await db.flush()


async def share_all(db: AsyncSession, caller: Caller, cycle: AppraisalCycle) -> int:
    """Share every review in calibration the caller may act on; how many.

    The route needs ``appraisals:manage`` and the HR person's own review and
    their manager's are left out, so the per-review rights come to this.
    """
    if cycle.status is CycleStatus.CLOSED:
        raise AppraisalConflictError("This cycle is closed.")
    appraisals, profiles = await visible_appraisals(db, caller, cycle)
    repo = AppraisalRepository(db, org_id=cycle.org_id)
    now, shared = datetime.now(UTC), 0
    for appraisal in appraisals:
        locked = await repo.lock_row(appraisal.id)
        if locked is None or locked.status is not AppraisalStatus.CALIBRATION:
            continue
        locked.status, locked.shared_at = AppraisalStatus.SHARED, now
        audit.record(
            db,
            org_id=cycle.org_id,
            actor_id=caller.user_id,
            subject_user_id=profiles[locked.profile_id].user_id,
            profile_id=locked.profile_id,
            action=EmployeeAuditAction.APPRAISAL_SHARED,
            target=locked.id,
        )
        shared += 1
    await db.flush()
    return shared


async def acknowledge(db: AsyncSession, ctx: AppraisalContext, reply: str) -> None:
    """The employee has read the result, with an optional reply HR sees."""
    await _lock(db, ctx)
    appraisal = ctx.appraisal
    if not (ctx.is_self and appraisal.status is AppraisalStatus.SHARED):
        raise AppraisalConflictError("There is no shared result to acknowledge.")
    appraisal.status = AppraisalStatus.ACKNOWLEDGED
    appraisal.acknowledged_at = datetime.now(UTC)
    crypto.seal(appraisal, "reply", reply.strip())
    _audit(db, ctx, EmployeeAuditAction.APPRAISAL_ACKNOWLEDGED)
    await db.flush()
