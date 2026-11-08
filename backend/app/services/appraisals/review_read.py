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

"""One appraisal as the caller may see it: evidence first, then the scores."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_enums import AppraisalStatus
from app.models.appraisal_goal import AppraisalGoal
from app.repositories.appraisal_check_in import AppraisalCheckInRepository
from app.repositories.appraisal_goal import AppraisalGoalRepository
from app.repositories.user import UserRepository
from app.repositories.work_facts_other import readable_boards
from app.schemas.appraisal_check_in import AiLine, CheckInNote, FactView, LinkRead
from app.schemas.appraisal_review import (
    AppraisalRead,
    ManagerOnly,
    ManagerScore,
    ReviewActions,
    ReviewGoal,
    SelfScore,
    TimelineMonth,
)
from app.services.appraisals import audit, crypto
from app.services.appraisals.access import AppraisalAccess
from app.services.appraisals.appraisal_context import AppraisalContext
from app.services.appraisals.context import Caller
from app.services.appraisals.evidence import ids_of
from app.services.appraisals.fact_view import board_ids, for_viewer


def _goal(goal: AppraisalGoal, access: AppraisalAccess) -> ReviewGoal:
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
        manager_reason=crypto.unseal(goal, "manager_reason") if manager else None,
    )


def _actions(ctx: AppraisalContext) -> ReviewActions:
    access, status = ctx.access, ctx.appraisal.status
    calibrating = status is AppraisalStatus.CALIBRATION
    return ReviewActions(
        edit_self=access.edit_self_score and status is AppraisalStatus.SELF_REVIEW,
        edit_manager=access.edit_manager_score and status is AppraisalStatus.MANAGER_REVIEW,
        send_back=access.send_back and calibrating,
        share=access.share and calibrating,
        acknowledge=ctx.is_self and status is AppraisalStatus.SHARED,
    )


async def read_review(
    db: AsyncSession, caller: Caller, ctx: AppraisalContext, *, log_view: bool = True
) -> AppraisalRead:
    """The appraisal for this viewer; someone else opening it is logged."""
    appraisal, profile, cycle, access = ctx.appraisal, ctx.profile, ctx.cycle, ctx.access
    if log_view:
        await audit.record_view(
            db,
            org_id=caller.org_id,
            actor_id=caller.user_id,
            subject_user_id=profile.user_id,
            profile_id=profile.id,
            target=appraisal.id,
        )
    repo = AppraisalCheckInRepository(db, org_id=caller.org_id)
    months = await repo.for_person_in_cycle(profile.id, cycle.id)
    every = [f for c in months for f in c.fact_refs or []] + list(appraisal.period_facts or [])
    boards = (
        set()
        if ctx.is_self
        else await readable_boards(
            db, caller.org_id, caller.user_id, caller.perms, board_ids(every)
        )
    )

    def view(facts: list[dict[str, object]]) -> list[FactView]:
        shown = for_viewer(facts, is_self=ctx.is_self, perms=caller.perms, boards=boards)
        return [FactView.model_validate(f) for f in shown]

    timeline = [
        TimelineMonth(
            check_in_id=c.id,
            period_start=c.period_start,
            status=c.status,
            facts=view(list(c.fact_refs or [])),
            note=CheckInNote.model_validate(crypto.unseal_json(c, "employee_note") or {}),
            links=[
                LinkRead(
                    id=link.id,
                    url=crypto.unseal(link, "url") or "",
                    title=crypto.unseal(link, "title") or "",
                    heading=link.heading,
                    goal_id=link.goal_id,
                )
                for link in await repo.links(c.id)
            ],
        )
        for c in months
    ]
    # As on a check-in: a viewer who can't open every fact gets no summary.
    hidden = appraisal.ai_period_summary is not None and any(
        f["private"]
        for f in for_viewer(every, is_self=ctx.is_self, perms=caller.perms, boards=boards)
    )
    lines = crypto.unseal_json(appraisal, "ai_period_summary") if not hidden else None
    goals = await AppraisalGoalRepository(db, org_id=caller.org_id).accepted_for_period(
        profile.id, cycle.period_start
    )
    users = UserRepository(db)
    person = await users.get_by_id_in_org(profile.user_id, caller.org_id)
    manager = await users.get_by_id_in_org(appraisal.manager_user_id, caller.org_id)
    hr_or_manager = not ctx.is_self and (access.edit_manager_score or access.view_calibration)
    return AppraisalRead(
        id=appraisal.id,
        user_id=profile.user_id,
        person_name=person.name if person else "",
        manager_name=manager.name if manager else None,
        cycle_name=cycle.name,
        period_start=cycle.period_start,
        period_end=cycle.period_end,
        self_due=cycle.self_due,
        manager_due=cycle.manager_due,
        ack_due=cycle.ack_due,
        status=appraisal.status,
        drafting_mode=appraisal.drafting_mode,
        summary_status=appraisal.period_summary_status,
        summary=[AiLine.model_validate(line) for line in lines or []],
        summary_hidden=hidden,
        timeline=timeline,
        period_facts=view(list(appraisal.period_facts or [])),
        goals=[_goal(g, access) for g in goals],
        self_score=SelfScore(
            band=appraisal.self_band,
            reason=crypto.unseal(appraisal, "self_reason") or "",
            evidence=ids_of(appraisal.self_evidence),
            submitted_at=appraisal.self_submitted_at,
        )
        if access.view_self_score
        else None,
        manager_score=ManagerScore(
            band=appraisal.manager_band,
            reason=crypto.unseal(appraisal, "manager_reason") or "",
            evidence=ids_of(appraisal.manager_evidence),
            final_band=appraisal.final_band if appraisal.manager_submitted_at else None,
            submitted_at=appraisal.manager_submitted_at,
        )
        if access.view_manager_score
        else None,
        manager_only=ManagerOnly(
            ready_next_level=appraisal.ready_next_level,
            performance_concern=appraisal.performance_concern,
            concern_note=crypto.unseal(appraisal, "concern_note") or "",
        )
        if access.view_manager_only
        else None,
        send_back_note=crypto.unseal(appraisal, "send_back_note") if hr_or_manager else None,
        reply=crypto.unseal(appraisal, "reply")
        if ctx.is_self or access.view_calibration
        else None,
        shared_at=appraisal.shared_at,
        acknowledged_at=appraisal.acknowledged_at,
        can=_actions(ctx),
    )
