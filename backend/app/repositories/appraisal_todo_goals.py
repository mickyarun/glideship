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

"""Goals on the to-do list, while goals are still open (before the review).

A primary manager's reports: confirmed goals, and the employee's proposals
to decide on. The caller's own: changes their manager suggested to one of
their goals. Each carries the cycle's "goals agreed by" date.
"""

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import ColumnElement, and_, func, select

from app.models.appraisal import Appraisal
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import AppraisalStatus, GoalStatus
from app.models.appraisal_goal import FROM_MANAGER, AppraisalGoal
from app.models.employee_profile import EmployeeProfile
from app.models.employee_reporting_manager import EmployeeReportingManager
from app.models.user import User
from app.repositories.appraisal_todo_base import TodoReads


@dataclass(frozen=True)
class GoalCount:
    """One report's goals in a period that hasn't reached its review."""

    appraisal_id: uuid.UUID
    person_name: str
    accepted: int
    proposed: int
    goals_due: date
    period_start: date
    enrolled_on: date


@dataclass(frozen=True)
class OwnChanges:
    """Changes the caller's manager suggested to their goals, waiting on them."""

    appraisal_id: uuid.UUID
    count: int
    goals_due: date
    manager_name: str


def from_manager() -> ColumnElement[bool]:
    """A proposal the manager wrote: the employee decides on it."""
    # Coalesced so "not from the manager" holds for proposals with no "from" key
    # (NULL would drop them). The JSONB path expression comes back untyped.
    source = func.coalesce(AppraisalGoal.suggestion_refs["from"].astext, "")
    wrote: ColumnElement[bool] = source == FROM_MANAGER
    return wrote


class AppraisalTodoGoalsRepository(TodoReads):
    """Goal reads for the to-do list, scoped to one org."""

    def _period_goals(self) -> ColumnElement[bool]:
        goal = AppraisalGoal
        return and_(
            goal.org_id == self._org,
            goal.profile_id == Appraisal.profile_id,
            goal.target_period_start == AppraisalCycle.period_start,
        )

    async def goal_counts(self, manager_user_id: uuid.UUID) -> list[GoalCount]:
        """Each report's confirmed goals, and the proposals the manager decides on."""
        goal = AppraisalGoal
        result = await self._db.execute(
            select(
                Appraisal.id,
                User.name,
                AppraisalCycle.goals_due,
                AppraisalCycle.period_start,
                Appraisal.created_at,
                func.count(goal.id).filter(goal.status == GoalStatus.ACCEPTED).label("accepted"),
                func.count(goal.id)
                .filter(goal.status == GoalStatus.PROPOSED, ~from_manager())
                .label("proposed"),
            )
            .join(AppraisalCycle, AppraisalCycle.id == Appraisal.cycle_id)
            .join(EmployeeReportingManager, self._primary(manager_user_id))
            .join(EmployeeProfile, EmployeeProfile.id == Appraisal.profile_id)
            .join(User, User.id == EmployeeProfile.user_id)
            .outerjoin(goal, self._period_goals())
            .where(*self._live(), Appraisal.status == AppraisalStatus.ENROLLED)
            .group_by(
                Appraisal.id,
                User.name,
                AppraisalCycle.goals_due,
                AppraisalCycle.period_start,
                Appraisal.created_at,
            )
        )
        return [
            GoalCount(
                r.id,
                r.name,
                r.accepted,
                r.proposed,
                r.goals_due,
                r.period_start,
                r.created_at.date(),
            )
            for r in result.all()
        ]

    async def own_changes(self, user_id: uuid.UUID) -> list[OwnChanges]:
        """The caller's goals their manager suggested changing, still to decide on."""
        goal = AppraisalGoal
        result = await self._db.execute(
            select(
                Appraisal.id, AppraisalCycle.goals_due, User.name, func.count(goal.id).label("n")
            )
            .join(AppraisalCycle, AppraisalCycle.id == Appraisal.cycle_id)
            .join(User, User.id == Appraisal.manager_user_id)
            .join(EmployeeProfile, EmployeeProfile.id == Appraisal.profile_id)
            .join(goal, self._period_goals())
            .where(
                *self._live(),
                EmployeeProfile.user_id == user_id,
                Appraisal.status == AppraisalStatus.ENROLLED,
                goal.status == GoalStatus.PROPOSED,
                from_manager(),
            )
            .group_by(Appraisal.id, AppraisalCycle.goals_due, User.name)
        )
        return [OwnChanges(r.id, r.n, r.goals_due, r.name) for r in result.all()]
