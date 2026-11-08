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

"""The manager's review: agree or change each goal and the band, then submit to HR.

While drafting, the manager's picks are kept on the row (``manager_band``
and each goal's ``manager_result``); only submitting fixes the final band
and results, so a later change in code can't move a shared result. Only
a submitted self-score can be agreed with. The two questions only the
manager answers are saved with it. The row is locked first, so a
send-back can't cross a submit.
"""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_enums import AppraisalStatus
from app.models.employee_audit_event import EmployeeAuditAction
from app.repositories.appraisal import AppraisalRepository
from app.schemas.appraisal_review import ManagerBody
from app.services.appraisals import audit, crypto
from app.services.appraisals.appraisal_context import AppraisalContext
from app.services.appraisals.errors import AppraisalConflictError, AppraisalInvalidError
from app.services.appraisals.evidence import evidence_pool, pick
from app.services.appraisals.review_rules import (
    BandDecision,
    GoalDecision,
    band_problem,
    final_band,
    final_result,
    goal_problem,
    submitted_band,
    submitted_result,
)
from app.services.appraisals.self_review import period_goals


def _open(ctx: AppraisalContext) -> None:
    if not (
        ctx.access.edit_manager_score and ctx.appraisal.status is AppraisalStatus.MANAGER_REVIEW
    ):
        raise AppraisalConflictError("This review isn't waiting for you.")


async def _apply(
    db: AsyncSession, ctx: AppraisalContext, body: ManagerBody, *, submit: bool
) -> None:
    await AppraisalRepository(db, org_id=ctx.appraisal.org_id).lock_row(ctx.appraisal.id)
    _open(ctx)
    appraisal = ctx.appraisal
    own_band = submitted_band(appraisal)
    pool = await evidence_pool(db, appraisal)
    goals = await period_goals(db, ctx)
    evidence = pick(pool, body.evidence)
    band = BandDecision(body.agree, body.band, body.reason, len(evidence))
    decisions = {str(g.goal_id): g for g in body.goals}
    if set(decisions) - set(goals):
        raise AppraisalInvalidError("That goal isn't one of this period's goals.")
    problems = []
    for key, goal in goals.items():
        item = decisions.get(key)
        decision = (
            GoalDecision(item.agree, item.result, item.reason)
            if item
            else GoalDecision(False, None, "")
        )
        own = submitted_result(appraisal, goal)
        goal.manager_result = final_result(own, decision)
        crypto.seal(
            goal, "manager_reason", decision.reason.strip() if not decision.agree else None
        )
        problems.append(goal_problem(own, decision))
    appraisal.manager_band = final_band(own_band, band)
    crypto.seal(appraisal, "manager_reason", body.reason.strip() if not body.agree else None)
    appraisal.manager_evidence = evidence
    appraisal.ready_next_level = body.ready_next_level
    appraisal.performance_concern = body.performance_concern
    crypto.seal(
        appraisal, "concern_note", body.concern_note.strip() if body.performance_concern else None
    )
    if submit:
        problem = band_problem(own_band, band) or next((p for p in problems if p), None)
        if problem:
            raise AppraisalInvalidError(problem)
        for goal in goals.values():
            goal.final_result = goal.manager_result
        appraisal.final_band = appraisal.manager_band
        appraisal.manager_submitted_at = datetime.now(UTC)
        appraisal.status = AppraisalStatus.CALIBRATION
        crypto.seal(appraisal, "send_back_note", None)
        audit.record(
            db,
            org_id=appraisal.org_id,
            actor_id=ctx.caller_id,
            subject_user_id=ctx.profile.user_id,
            profile_id=ctx.profile.id,
            action=EmployeeAuditAction.APPRAISAL_SCORED,
            target=appraisal.id,
        )
    await db.flush()


async def save_manager(db: AsyncSession, ctx: AppraisalContext, body: ManagerBody) -> None:
    """Keep the manager's draft."""
    await _apply(db, ctx, body, submit=False)


async def send_manager(db: AsyncSession, ctx: AppraisalContext, body: ManagerBody) -> None:
    """Check the rules and send the review to HR."""
    await _apply(db, ctx, body, submit=True)
