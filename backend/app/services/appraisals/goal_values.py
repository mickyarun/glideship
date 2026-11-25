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

"""Each goal's value across the period, month by month, for one viewer.

Values are the person's writing on a check-in, so only check-ins they
sent count for anyone else; the person sees all of theirs. Months with
no value for a goal are left out rather than shown empty.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.appraisal_check_in import AppraisalCheckInRepository
from app.repositories.appraisal_goal import AppraisalGoalRepository
from app.repositories.appraisal_goal_value import AppraisalGoalValueRepository
from app.schemas.appraisal_goal_values import GoalMonthValue, GoalValues
from app.services.appraisals import crypto
from app.services.appraisals.access import reads_content
from app.services.appraisals.appraisal_context import AppraisalContext


async def read_goal_values(db: AsyncSession, ctx: AppraisalContext) -> list[GoalValues]:
    """The period's confirmed goals, each with its value per readable check-in, oldest first."""
    org_id, profile = ctx.cycle.org_id, ctx.profile
    months = await AppraisalCheckInRepository(db, org_id=org_id).for_person_in_cycle(
        profile.id, ctx.cycle.id
    )
    readable = {
        c.id: c
        for c in months
        if reads_content(ctx.caller_id, profile.user_id, c.sent_at is not None)
    }
    values = await AppraisalGoalValueRepository(db, org_id=org_id).for_check_ins(list(readable))
    goals = await AppraisalGoalRepository(db, org_id=org_id).accepted_for_period(
        profile.id, ctx.cycle.period_start
    )
    out = []
    for goal in goals:
        mine = sorted(
            (v for v in values if v.goal_id == goal.id),
            key=lambda v: readable[v.check_in_id].period_start,
        )
        out.append(
            GoalValues(
                goal_id=goal.id,
                position=goal.position or 0,
                title=crypto.unseal(goal, "title") or "",
                measure=crypto.unseal(goal, "measure"),
                values=[
                    GoalMonthValue(
                        check_in_id=v.check_in_id,
                        period_start=readable[v.check_in_id].period_start,
                        value=crypto.unseal(v, "value") or "",
                        source_note=crypto.unseal(v, "source_note"),
                        source_url=crypto.unseal(v, "source_url"),
                    )
                    for v in mine
                ],
            )
        )
    return out
