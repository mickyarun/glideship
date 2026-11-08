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

"""Manager feedback for one viewer: one item, and the feedback as it
appears on the employee's check-in (the team list: :mod:`.feedback_team`)."""

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import FeedbackStatus, GoalCheck
from app.models.appraisal_manager_feedback import AppraisalManagerFeedback
from app.repositories.appraisal_check_in import AppraisalCheckInRepository
from app.repositories.appraisal_feedback import AppraisalFeedbackRepository
from app.repositories.appraisal_goal import AppraisalGoalRepository
from app.repositories.user import UserRepository
from app.schemas.appraisal_feedback import (
    FeedbackCheckIn,
    FeedbackGoal,
    FeedbackRead,
    FeedbackShown,
)
from app.services.appraisals import audit, crypto
from app.services.appraisals.context import Caller, CheckInContext
from app.services.appraisals.feedback import FeedbackContext, written
from app.services.appraisals.org_clock import org_today


def is_overdue(item: AppraisalManagerFeedback, today: date) -> bool:
    """Still open after its due date (pure)."""
    return item.status is FeedbackStatus.OPEN and today > item.due_on


def in_period(check_in: AppraisalCheckIn, item: AppraisalManagerFeedback) -> bool:
    """The check-in is one of those the item covers (pure)."""
    return item.period_start <= check_in.period_start <= item.period_end


async def _goals(
    db: AsyncSession, item: AppraisalManagerFeedback, cycle: AppraisalCycle | None
) -> list[FeedbackGoal]:
    """This period's goals with the manager's statuses, for quarterly items."""
    if cycle is None:
        return []
    accepted = await AppraisalGoalRepository(db, org_id=item.org_id).accepted_for_period(
        item.profile_id, cycle.period_start
    )
    notes: dict[str, str] = crypto.unseal_json(item, "goal_notes") or {}
    out = []
    for goal in accepted:
        key = str(goal.id)
        status = (item.goal_status or {}).get(key, {}).get("status")
        out.append(
            FeedbackGoal(
                id=goal.id,
                title=crypto.unseal(goal, "title") or "",
                status=GoalCheck(status) if status else None,
                note=notes.get(key, ""),
            )
        )
    return out


async def read_feedback(
    db: AsyncSession, caller: Caller, ctx: FeedbackContext, *, log_view: bool = True
) -> FeedbackRead:
    """The item as ``caller`` may see it; opening someone else's logs a view."""
    item, profile = ctx.item, ctx.profile
    if log_view:
        await audit.record_view(
            db,
            org_id=caller.org_id,
            actor_id=caller.user_id,
            subject_user_id=profile.user_id,
            profile_id=profile.id,
            target=ctx.appraisal.id if ctx.appraisal else item.id,
        )
    users = UserRepository(db)
    person = await users.get_by_id_in_org(profile.user_id, caller.org_id)
    manager = await users.get_by_id_in_org(item.manager_user_id, caller.org_id)
    check_ins = await AppraisalCheckInRepository(db, org_id=caller.org_id).for_person_in_cycle(
        profile.id, item.cycle_id
    )
    return FeedbackRead(
        id=item.id,
        profile_id=profile.id,
        person_name=person.name if person else "",
        manager_name=manager.name if manager else None,
        period_start=item.period_start,
        period_end=item.period_end,
        cadence=item.cadence,
        due_on=item.due_on,
        status=item.status,
        done_at=item.done_at,
        overdue=is_overdue(item, await org_today(db, caller.org_id)),
        can_edit=ctx.can_edit,
        keep=crypto.unseal(item, "keep_note") or "",
        try_next=crypto.unseal(item, "try_note") or "",
        goals=await _goals(db, item, ctx.cycle),
        check_ins=[
            FeedbackCheckIn(
                id=c.id,
                period_start=c.period_start,
                status=c.status,
                closed=c.closed_at is not None,
            )
            for c in check_ins
            if in_period(c, item)
        ],
    )


async def shown_on_check_in(db: AsyncSession, ctx: CheckInContext) -> FeedbackShown | None:
    """The feedback answering this check-in, once the manager has written some.

    Monthly feedback sits on its month; quarterly feedback on the quarter's
    last check-in.
    """
    if not ctx.access.view_feedback:
        return None
    check_in = ctx.check_in
    item = await AppraisalFeedbackRepository(db, org_id=check_in.org_id).covering(
        check_in.cycle_id, check_in.profile_id, check_in.period_end
    )
    if item is None or not written(item):
        return None
    manager = await UserRepository(db).get_by_id_in_org(item.manager_user_id, item.org_id)
    return FeedbackShown(
        manager_name=manager.name if manager else None,
        period_start=item.period_start,
        period_end=item.period_end,
        cadence=item.cadence,
        done=item.status is FeedbackStatus.DONE,
        keep=crypto.unseal(item, "keep_note") or "",
        try_next=crypto.unseal(item, "try_note") or "",
        goals=[g for g in await _goals(db, item, ctx.cycle) if g.status is not None],
    )
