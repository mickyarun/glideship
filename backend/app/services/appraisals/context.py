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

"""Who is asking about whose appraisal records, resolved once per request.

Every read and write of a check-in goes through ``check_in_context``: it
loads the record, works out the caller's relation from the current
manager links and returns their rights. Anything the caller may not see
raises "not found".
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permission_deps import PermissionSet
from app.models.appraisal import Appraisal
from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import AppraisalStatus, CycleStatus
from app.models.employee_profile import EmployeeProfile
from app.repositories.appraisal import AppraisalRepository
from app.repositories.appraisal_check_in import AppraisalCheckInRepository
from app.repositories.appraisal_cycle import AppraisalCycleRepository
from app.repositories.employee_profile import EmployeeProfileRepository
from app.repositories.employee_reporting_manager import EmployeeReportingManagerRepository
from app.services.appraisals.access import AppraisalAccess, Stage, access_for, relation_for
from app.services.appraisals.errors import AppraisalNotFoundError

NOT_FOUND = "Check-in not found."


@dataclass(frozen=True)
class Caller:
    """The person making the request."""

    user_id: uuid.UUID
    org_id: uuid.UUID
    perms: PermissionSet


@dataclass(frozen=True)
class CheckInContext:
    """A check-in with everything needed to show or change it."""

    check_in: AppraisalCheckIn
    profile: EmployeeProfile
    appraisal: Appraisal | None
    cycle: AppraisalCycle | None
    access: AppraisalAccess

    @property
    def is_open(self) -> bool:
        """Still editable: not closed, and its cycle and appraisal still running."""
        return self.check_in.closed_at is None and self.access.edit_check_ins


def stage_for(appraisal: Appraisal | None, cycle: AppraisalCycle | None) -> Stage:
    """The access stage of an appraisal (an empty one when there is none)."""
    locked = (appraisal is not None and appraisal.status is AppraisalStatus.WITHDRAWN) or (
        cycle is not None and cycle.status is CycleStatus.CLOSED
    )
    if appraisal is None:
        return Stage(editable=not locked)
    return Stage(
        self_submitted=appraisal.self_submitted_at is not None,
        manager_submitted=appraisal.manager_submitted_at is not None,
        shared=appraisal.shared_at is not None,
        editable=not locked,
    )


async def rights_over(
    db: AsyncSession,
    caller: Caller,
    profile: EmployeeProfile,
    appraisal: Appraisal | None,
    stage: Stage,
) -> AppraisalAccess:
    """The caller's rights over one person's records."""
    links = EmployeeReportingManagerRepository(db, org_id=caller.org_id)
    own = await EmployeeProfileRepository(db, org_id=caller.org_id).get_by_user(caller.user_id)
    profile_ids = [profile.id, *([own.id] if own else [])]
    managers = await links.list_for_profiles(profile_ids)
    subject_managers = [m for m in managers.get(profile.id, []) if m.is_active]
    primary = (
        appraisal.manager_user_id
        if appraisal
        else next((m.user_id for m in subject_managers if m.is_primary), None)
    )
    relation = relation_for(
        caller.user_id,
        profile.user_id,
        primary,
        {m.user_id for m in subject_managers},
        {m.user_id for m in managers.get(own.id, [])} if own else (),
    )
    return access_for(caller.perms, relation, stage)


async def check_in_context(
    db: AsyncSession, caller: Caller, check_in_id: uuid.UUID
) -> CheckInContext:
    """Load a check-in the caller may see; "not found" otherwise."""
    check_in = await AppraisalCheckInRepository(db, org_id=caller.org_id).get_by_id(check_in_id)
    if check_in is None:
        raise AppraisalNotFoundError(NOT_FOUND)
    profile = await EmployeeProfileRepository(db, org_id=caller.org_id).get_by_id(
        check_in.profile_id
    )
    if profile is None:
        raise AppraisalNotFoundError(NOT_FOUND)
    appraisal = await AppraisalRepository(db, org_id=caller.org_id).for_profile_in_cycle(
        profile.id, check_in.cycle_id
    )
    cycle = await AppraisalCycleRepository(db, org_id=caller.org_id).get_by_id(check_in.cycle_id)
    access = await rights_over(db, caller, profile, appraisal, stage_for(appraisal, cycle))
    if not access.any:
        raise AppraisalNotFoundError(NOT_FOUND)
    return CheckInContext(check_in, profile, appraisal, cycle, access)
