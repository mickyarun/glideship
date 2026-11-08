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

Each step is audited. Sharing in bulk shares every review in calibration
that the HR person may act on, one by one under the same rules.
"""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import AppraisalStatus
from app.models.employee_audit_event import EmployeeAuditAction
from app.services.appraisals import audit, crypto
from app.services.appraisals.appraisal_context import AppraisalContext, appraisal_context
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


async def send_back(db: AsyncSession, ctx: AppraisalContext, note: str) -> None:
    """Return the review to the manager with a note they read."""
    appraisal = ctx.appraisal
    if not (ctx.access.send_back and appraisal.status is AppraisalStatus.CALIBRATION):
        raise AppraisalConflictError("Only a review waiting for HR can be sent back.")
    appraisal.status = AppraisalStatus.MANAGER_REVIEW
    appraisal.manager_submitted_at = None
    appraisal.final_band = None
    appraisal.review_notified_at = None
    crypto.seal(appraisal, "send_back_note", note.strip())
    _audit(db, ctx, EmployeeAuditAction.APPRAISAL_SENT_BACK)
    await db.flush()


async def share(db: AsyncSession, ctx: AppraisalContext) -> None:
    """Show the result to the employee."""
    appraisal = ctx.appraisal
    if not (ctx.access.share and appraisal.status is AppraisalStatus.CALIBRATION):
        raise AppraisalConflictError("Only a review waiting for HR can be shared.")
    appraisal.status = AppraisalStatus.SHARED
    appraisal.shared_at = datetime.now(UTC)
    _audit(db, ctx, EmployeeAuditAction.APPRAISAL_SHARED)
    await db.flush()


async def share_all(db: AsyncSession, caller: Caller, cycle: AppraisalCycle) -> int:
    """Share every review in calibration the caller may act on; how many."""
    shared = 0
    for appraisal in await visible_appraisals(db, caller, cycle):
        if appraisal.status is not AppraisalStatus.CALIBRATION:
            continue
        ctx = await appraisal_context(db, caller, appraisal.id)
        if ctx.access.share:
            await share(db, ctx)
            shared += 1
    return shared


async def acknowledge(db: AsyncSession, ctx: AppraisalContext, reply: str) -> None:
    """The employee has read the result, with an optional reply HR sees."""
    appraisal = ctx.appraisal
    if not (ctx.is_self and appraisal.status is AppraisalStatus.SHARED):
        raise AppraisalConflictError("There is no shared result to acknowledge.")
    appraisal.status = AppraisalStatus.ACKNOWLEDGED
    appraisal.acknowledged_at = datetime.now(UTC)
    crypto.seal(appraisal, "reply", reply.strip())
    await db.flush()
