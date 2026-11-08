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

"""Who is asking about one appraisal or one goal, resolved once per request.

Like ``check_in_context``: it loads the record, works out the caller's
rights from the current manager links, and answers "not found" for
anything the caller may not see.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal import Appraisal
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_goal import AppraisalGoal
from app.models.employee_profile import EmployeeProfile
from app.repositories.appraisal import AppraisalRepository
from app.repositories.appraisal_cycle import AppraisalCycleRepository
from app.repositories.appraisal_goal import AppraisalGoalRepository
from app.repositories.employee_profile import EmployeeProfileRepository
from app.services.appraisals.access import AppraisalAccess
from app.services.appraisals.context import Caller, rights_over, stage_for
from app.services.appraisals.errors import AppraisalNotFoundError

NOT_FOUND = "Appraisal not found."


@dataclass(frozen=True)
class AppraisalContext:
    """An appraisal with its person, cycle and the caller's rights."""

    appraisal: Appraisal
    profile: EmployeeProfile
    cycle: AppraisalCycle
    access: AppraisalAccess
    caller_id: uuid.UUID

    @property
    def is_self(self) -> bool:
        """The caller is the person the appraisal is about."""
        return self.profile.user_id == self.caller_id


async def appraisal_context(
    db: AsyncSession, caller: Caller, appraisal_id: uuid.UUID
) -> AppraisalContext:
    """Load an appraisal the caller may see; "not found" otherwise."""
    appraisal = await AppraisalRepository(db, org_id=caller.org_id).get_by_id(appraisal_id)
    if appraisal is None:
        raise AppraisalNotFoundError(NOT_FOUND)
    return await _context(db, caller, appraisal)


async def _context(db: AsyncSession, caller: Caller, appraisal: Appraisal) -> AppraisalContext:
    profile = await EmployeeProfileRepository(db, org_id=caller.org_id).get_by_id(
        appraisal.profile_id
    )
    cycle = await AppraisalCycleRepository(db, org_id=caller.org_id).get_by_id(appraisal.cycle_id)
    if profile is None or cycle is None:
        raise AppraisalNotFoundError(NOT_FOUND)
    access = await rights_over(db, caller, profile, appraisal, stage_for(appraisal, cycle))
    if not access.any:
        raise AppraisalNotFoundError(NOT_FOUND)
    return AppraisalContext(appraisal, profile, cycle, access, caller.user_id)


async def goal_context(
    db: AsyncSession, caller: Caller, goal_id: uuid.UUID
) -> tuple[AppraisalGoal, AppraisalContext]:
    """Load a goal in a cycle and its appraisal; "not found" otherwise.

    A goal set ahead of a cycle that doesn't exist yet is reached through
    the growth conversation instead, so it isn't found here.
    """
    goal = await AppraisalGoalRepository(db, org_id=caller.org_id).get_by_id(goal_id)
    if goal is None or goal.cycle_id is None:
        raise AppraisalNotFoundError("Goal not found.")
    appraisal = await AppraisalRepository(db, org_id=caller.org_id).for_profile_in_cycle(
        goal.profile_id, goal.cycle_id
    )
    if appraisal is None:
        raise AppraisalNotFoundError("Goal not found.")
    return goal, await _context(db, caller, appraisal)
