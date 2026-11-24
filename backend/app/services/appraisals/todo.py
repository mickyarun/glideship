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

"""The caller's appraisal to-do list: what to do now, whose, and by when.

Three parts, each only for those it applies to. Everyone: their open
check-in to send, their review to write, their result to read, and
changes their manager suggested to their goals. A
primary manager, for the appraisals they score: notes owed on sent
check-ins (and those still waiting on one), reviews to send on to HR,
proposed goals to confirm and people below the org's fewest goals (both
due by the cycle's goals date). HR
(``appraisals:manage``): cycles whose period has ended and whose reviews
can open, and reviews waiting in the fairness check. Late work comes first, then by due date.
"""

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions_people import APPRAISALS_MANAGE
from app.models.appraisal_enums import AppraisalStatus, CycleStatus
from app.repositories.appraisal_cycle import AppraisalCycleRepository
from app.repositories.appraisal_todo import AppraisalTodoRepository
from app.repositories.appraisal_todo_goals import AppraisalTodoGoalsRepository
from app.schemas.appraisal_todo import TodoItem, TodoKind, TodoRole, TodoTarget
from app.services.appraisals.context import Caller
from app.services.appraisals.cycle_people import goals_due_for
from app.services.appraisals.due_dates import is_late
from app.services.appraisals.org_clock import org_today
from app.services.appraisals.settings import goal_floor


def _decide_by(goals_due: date, today: date) -> date | None:
    """A proposal to decide on is due by the goals date while it's ahead; one
    that turns up later has no date, so it is never late the moment it appears."""
    return goals_due if goals_due >= today else None


def _item(today: date, **fields: object) -> TodoItem:
    due = fields.get("due_on")
    late = isinstance(due, date) and is_late(due, None, today)
    return TodoItem.model_validate({**fields, "late": late})


async def _own(
    repo: AppraisalTodoRepository,
    goals: AppraisalTodoGoalsRepository,
    caller: Caller,
    today: date,
) -> list[TodoItem]:
    out = [
        _item(
            today,
            kind=TodoKind.CHECK_IN,
            role=TodoRole.OWN,
            due_on=row.due_on,
            target=TodoTarget.CHECK_IN,
            target_id=row.id,
        )
        for row in await repo.own_check_ins(caller.user_id)
    ]
    for row in await repo.own_reviews(caller.user_id):
        shared = row.status is AppraisalStatus.SHARED
        out.append(
            _item(
                today,
                kind=TodoKind.READ_RESULT if shared else TodoKind.SELF_REVIEW,
                role=TodoRole.OWN,
                due_on=row.due_on,
                target=TodoTarget.REVIEW,
                target_id=row.id,
            )
        )
    out += [
        _item(
            today,
            kind=TodoKind.CONFIRM_CHANGE,
            role=TodoRole.OWN,
            # Who suggested it, for "Daniel suggested a change".
            person_name=row.manager_name,
            due_on=_decide_by(row.goals_due, today),
            target=TodoTarget.GOALS,
            target_id=row.appraisal_id,
            count=row.count,
        )
        for row in await goals.own_changes(caller.user_id)
    ]
    return out


async def _team(
    db: AsyncSession,
    repo: AppraisalTodoRepository,
    goal_repo: AppraisalTodoGoalsRepository,
    caller: Caller,
    today: date,
) -> list[TodoItem]:
    team = {"role": TodoRole.TEAM}
    out = [
        _item(
            today,
            # No due date yet: the note waits on the report's check-in, never late.
            kind=TodoKind.NOTE if row.due_on else TodoKind.WAITING_ON_CHECK_IN,
            person_name=row.person_name,
            due_on=row.due_on,
            target=TodoTarget.FEEDBACK,
            target_id=row.id,
            **team,
        )
        for row in await repo.notes_to_send(caller.user_id)
    ]
    out += [
        _item(
            today,
            kind=TodoKind.MANAGER_REVIEW,
            person_name=row.person_name,
            due_on=row.due_on,
            target=TodoTarget.REVIEW,
            target_id=row.id,
            **team,
        )
        for row in await repo.reviews_to_write(caller.user_id)
    ]
    floor = await goal_floor(db, caller.org_id)
    for goals in await goal_repo.goal_counts(caller.user_id):
        common = {
            "person_name": goals.person_name,
            "target": TodoTarget.GOALS,
            "target_id": goals.appraisal_id,
            **team,
        }
        if goals.proposed:
            decide = _decide_by(goals.goals_due, today)
            out.append(
                _item(
                    today,
                    kind=TodoKind.CONFIRM_GOALS,
                    count=goals.proposed,
                    due_on=decide,
                    **common,
                )
            )
        if goals.accepted < floor:
            due = goals_due_for(goals.goals_due, goals.period_start, goals.enrolled_on)
            out.append(
                _item(
                    today,
                    kind=TodoKind.SET_GOALS,
                    count=floor - goals.accepted,
                    due_on=due,
                    **common,
                )
            )
    return out


async def _cycles(db: AsyncSession, caller: Caller, today: date) -> list[TodoItem]:
    out = []
    for cycle in await AppraisalCycleRepository(db, org_id=caller.org_id).waiting_on_hr():
        common = {
            "role": TodoRole.CYCLES,
            "cycle_name": cycle.name,
            "target": TodoTarget.CYCLE,
            "target_id": cycle.id,
        }
        if cycle.status is CycleStatus.ACTIVE and cycle.period_end < today:
            out.append(_item(today, kind=TodoKind.OPEN_REVIEWS, **common))
        if cycle.in_check:
            out.append(_item(today, kind=TodoKind.FAIRNESS_CHECK, count=cycle.in_check, **common))
    return out


async def todo_list(db: AsyncSession, caller: Caller) -> list[TodoItem]:
    """Everything the caller has to do in appraisals now, late first, then by due date."""
    today = await org_today(db, caller.org_id)
    repo = AppraisalTodoRepository(db, org_id=caller.org_id, today=today)
    goals = AppraisalTodoGoalsRepository(db, org_id=caller.org_id, today=today)
    items = await _own(repo, goals, caller, today) + await _team(db, repo, goals, caller, today)
    if caller.perms.has(APPRAISALS_MANAGE):
        items += await _cycles(db, caller, today)
    return sorted(items, key=lambda i: (not i.late, i.due_on is None, i.due_on or today))
