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

"""Lists of appraisals: the caller's own, and their direct reports'."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal import Appraisal
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import GoalStatus
from app.repositories.appraisal import AppraisalRepository
from app.repositories.appraisal_cycle import AppraisalCycleRepository
from app.repositories.appraisal_goal import AppraisalGoalRepository
from app.repositories.employee_profile import EmployeeProfileRepository
from app.repositories.user import UserRepository
from app.schemas.appraisal_goal import AppraisalSummary
from app.services.appraisals.context import Caller


async def _summaries(
    db: AsyncSession,
    caller: Caller,
    appraisals: list[Appraisal],
    users: dict[uuid.UUID, uuid.UUID],
) -> list[AppraisalSummary]:
    """Rows for these appraisals; ``users`` maps each profile to its user."""
    cycles: dict[uuid.UUID, AppraisalCycle] = {}
    repo = AppraisalCycleRepository(db, org_id=caller.org_id)
    for cycle_id in {a.cycle_id for a in appraisals}:
        cycle = await repo.get_by_id(cycle_id)
        if cycle is not None:
            cycles[cycle_id] = cycle
    counts = await AppraisalGoalRepository(db, org_id=caller.org_id).status_counts(
        list({a.profile_id for a in appraisals})
    )
    names = {u.id: u.name for u in await UserRepository(db).get_many_by_ids(list(users.values()))}
    rows = []
    for appraisal in appraisals:
        cycle = cycles.get(appraisal.cycle_id)
        user_id = users.get(appraisal.profile_id)
        if cycle is None or user_id is None:
            continue
        key = (appraisal.profile_id, cycle.period_start)
        rows.append(
            AppraisalSummary(
                id=appraisal.id,
                user_id=user_id,
                person_name=names.get(user_id, ""),
                cycle_name=cycle.name,
                period_start=cycle.period_start,
                period_end=cycle.period_end,
                status=appraisal.status,
                goals_accepted=counts.get((*key, GoalStatus.ACCEPTED), 0),
                goals_proposed=counts.get((*key, GoalStatus.PROPOSED), 0),
            )
        )
    return sorted(rows, key=lambda r: (r.period_start, r.person_name.lower()), reverse=True)


async def my_appraisals(db: AsyncSession, caller: Caller) -> list[AppraisalSummary]:
    """The caller's appraisals, newest period first."""
    profile = await EmployeeProfileRepository(db, org_id=caller.org_id).get_by_user(caller.user_id)
    if profile is None:
        return []
    appraisals = await AppraisalRepository(db, org_id=caller.org_id).for_profiles([profile.id])
    return await _summaries(db, caller, appraisals, {profile.id: caller.user_id})


async def team_appraisals(db: AsyncSession, caller: Caller) -> list[AppraisalSummary]:
    """The caller's direct reports' appraisals, newest period first."""
    repo = AppraisalRepository(db, org_id=caller.org_id)
    profiles = await repo.profiles_by_id(await repo.report_profile_ids(caller.user_id))
    appraisals = await repo.for_profiles(list(profiles))
    return await _summaries(db, caller, appraisals, {p.id: p.user_id for p in profiles.values()})
