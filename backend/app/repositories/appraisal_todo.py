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

"""What each person has to do in appraisals, read in a few queries.

The caller's own open work, and the work they owe as a primary manager
(only reports whose primary manager they are now, and only appraisals
they score). Withdrawn appraisals and closed cycles never show. HR's
cycles: :meth:`.AppraisalCycleRepository.waiting_on_hr`.
"""

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import ColumnElement, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal import Appraisal
from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import AppraisalStatus, CycleStatus, GoalStatus
from app.models.appraisal_goal import AppraisalGoal
from app.models.appraisal_manager_feedback import AppraisalManagerFeedback
from app.models.employee_profile import EmployeeProfile
from app.models.employee_reporting_manager import EmployeeReportingManager
from app.models.user import User


@dataclass(frozen=True)
class TodoRow:
    """One piece of work: what it is, whose, by when."""

    id: uuid.UUID
    person_name: str
    due_on: date | None
    status: AppraisalStatus | None = None


@dataclass(frozen=True)
class GoalCount:
    """One report's goals in a period that hasn't reached its review."""

    appraisal_id: uuid.UUID
    person_name: str
    accepted: int
    proposed: int


class AppraisalTodoRepository:
    """To-do reads for one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        """Initialize the repository."""
        self._db = db
        self._org = org_id

    def _live(self) -> list[ColumnElement[bool]]:
        """Appraisals still in progress, in cycles that haven't closed."""
        return [
            Appraisal.org_id == self._org,
            Appraisal.status != AppraisalStatus.WITHDRAWN,
            AppraisalCycle.status != CycleStatus.CLOSED,
        ]

    def _primary(self, manager_user_id: uuid.UUID) -> ColumnElement[bool]:
        """The caller is the person's primary manager and scores their appraisal."""
        return and_(
            EmployeeReportingManager.org_id == self._org,
            EmployeeReportingManager.profile_id == Appraisal.profile_id,
            EmployeeReportingManager.manager_user_id == manager_user_id,
            EmployeeReportingManager.is_primary.is_(True),
            Appraisal.manager_user_id == manager_user_id,
        )

    async def own_check_ins(self, user_id: uuid.UUID) -> list[TodoRow]:
        """The caller's open check-ins not sent yet."""
        result = await self._db.execute(
            select(AppraisalCheckIn.id, AppraisalCheckIn.due_on)
            .join(EmployeeProfile, EmployeeProfile.id == AppraisalCheckIn.profile_id)
            .join(
                Appraisal,
                and_(
                    Appraisal.profile_id == AppraisalCheckIn.profile_id,
                    Appraisal.cycle_id == AppraisalCheckIn.cycle_id,
                ),
            )
            .join(AppraisalCycle, AppraisalCycle.id == Appraisal.cycle_id)
            .where(
                *self._live(),
                EmployeeProfile.user_id == user_id,
                AppraisalCheckIn.closed_at.is_(None),
                AppraisalCheckIn.sent_at.is_(None),
            )
        )
        return [TodoRow(row.id, "", row.due_on) for row in result.all()]

    async def own_reviews(self, user_id: uuid.UUID) -> list[TodoRow]:
        """The caller's appraisals waiting on them: their review, or reading the result."""
        result = await self._db.execute(
            select(
                Appraisal.id,
                Appraisal.status,
                AppraisalCycle.self_due,
                AppraisalCycle.ack_due,
            )
            .join(AppraisalCycle, AppraisalCycle.id == Appraisal.cycle_id)
            .join(EmployeeProfile, EmployeeProfile.id == Appraisal.profile_id)
            .where(
                *self._live(),
                EmployeeProfile.user_id == user_id,
                Appraisal.status.in_([AppraisalStatus.SELF_REVIEW, AppraisalStatus.SHARED]),
            )
        )
        return [
            TodoRow(
                row.id,
                "",
                row.ack_due if row.status is AppraisalStatus.SHARED else row.self_due,
                row.status,
            )
            for row in result.all()
        ]

    async def notes_to_send(self, manager_user_id: uuid.UUID) -> list[TodoRow]:
        """Notes the caller owes: their check-in was sent, the note wasn't."""
        item = AppraisalManagerFeedback
        result = await self._db.execute(
            select(item.id, item.due_on, User.name)
            .join(
                Appraisal,
                and_(Appraisal.profile_id == item.profile_id, Appraisal.cycle_id == item.cycle_id),
            )
            .join(AppraisalCycle, AppraisalCycle.id == Appraisal.cycle_id)
            .join(EmployeeReportingManager, self._primary(manager_user_id))
            .join(EmployeeProfile, EmployeeProfile.id == item.profile_id)
            .join(User, User.id == EmployeeProfile.user_id)
            .where(
                *self._live(),
                item.manager_user_id == manager_user_id,
                item.sent_at.is_(None),
                item.due_on.is_not(None),
            )
        )
        return [TodoRow(row.id, row.name, row.due_on) for row in result.all()]

    async def reviews_to_write(self, manager_user_id: uuid.UUID) -> list[TodoRow]:
        """Reviews sent to the caller, as primary manager, and not yet sent on to HR."""
        result = await self._db.execute(
            select(Appraisal.id, AppraisalCycle.manager_due, User.name)
            .join(AppraisalCycle, AppraisalCycle.id == Appraisal.cycle_id)
            .join(EmployeeReportingManager, self._primary(manager_user_id))
            .join(EmployeeProfile, EmployeeProfile.id == Appraisal.profile_id)
            .join(User, User.id == EmployeeProfile.user_id)
            .where(*self._live(), Appraisal.status == AppraisalStatus.MANAGER_REVIEW)
        )
        return [TodoRow(row.id, row.name, row.manager_due) for row in result.all()]

    async def goal_counts(self, manager_user_id: uuid.UUID) -> list[GoalCount]:
        """Each report's confirmed and proposed goals, while their goals are still open."""
        goal = AppraisalGoal
        counted = and_(
            goal.org_id == self._org,
            goal.profile_id == Appraisal.profile_id,
            goal.target_period_start == AppraisalCycle.period_start,
        )
        result = await self._db.execute(
            select(
                Appraisal.id,
                User.name,
                func.count(goal.id).filter(goal.status == GoalStatus.ACCEPTED).label("accepted"),
                func.count(goal.id).filter(goal.status == GoalStatus.PROPOSED).label("proposed"),
            )
            .join(AppraisalCycle, AppraisalCycle.id == Appraisal.cycle_id)
            .join(EmployeeReportingManager, self._primary(manager_user_id))
            .join(EmployeeProfile, EmployeeProfile.id == Appraisal.profile_id)
            .join(User, User.id == EmployeeProfile.user_id)
            .outerjoin(goal, counted)
            .where(*self._live(), Appraisal.status == AppraisalStatus.ENROLLED)
            .group_by(Appraisal.id, User.name)
        )
        return [GoalCount(r.id, r.name, r.accepted, r.proposed) for r in result.all()]
