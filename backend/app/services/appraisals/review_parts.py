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

"""Parts of a review read: each goal for the viewer, and what they may do now."""

from app.models.appraisal_enums import AppraisalStatus
from app.models.appraisal_goal import AppraisalGoal
from app.schemas.appraisal_review import ReviewActions, ReviewGoal
from app.services.appraisals import crypto
from app.services.appraisals.access import AppraisalAccess
from app.services.appraisals.appraisal_context import AppraisalContext
from app.services.appraisals.evidence import ids_of


def review_goal(goal: AppraisalGoal, access: AppraisalAccess) -> ReviewGoal:
    """One goal's results as the viewer may see them."""
    own, manager = access.view_self_score, access.view_manager_score
    return ReviewGoal(
        id=goal.id,
        position=goal.position,
        title=crypto.unseal(goal, "title") or "",
        measure=crypto.unseal(goal, "measure") or "",
        added_mid_period=goal.added_mid_period,
        accepted_at=goal.accepted_at,
        self_result=goal.self_result if own else None,
        self_reason=crypto.unseal(goal, "self_reason") if own else None,
        self_evidence=ids_of(goal.self_evidence) if own else [],
        result=goal.final_result if manager else None,
        draft_result=goal.manager_result if access.edit_manager_score else None,
        manager_reason=crypto.unseal(goal, "manager_reason") if manager else None,
    )


def review_actions(ctx: AppraisalContext) -> ReviewActions:
    """What the viewer may do with the review now."""
    access, status = ctx.access, ctx.appraisal.status
    calibrating = status is AppraisalStatus.CALIBRATION
    return ReviewActions(
        edit_self=access.edit_self_score and status is AppraisalStatus.SELF_REVIEW,
        edit_manager=access.edit_manager_score and status is AppraisalStatus.MANAGER_REVIEW,
        send_back=access.send_back and calibrating,
        share=access.share and calibrating,
        acknowledge=ctx.is_self and status is AppraisalStatus.SHARED,
    )
