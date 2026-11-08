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

"""Lists of check-ins: the caller's own, and their direct reports' latest."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_check_in import AppraisalCheckIn
from app.repositories.appraisal import AppraisalRepository
from app.repositories.appraisal_check_in import AppraisalCheckInRepository
from app.repositories.employee_profile import EmployeeProfileRepository
from app.repositories.user import UserRepository
from app.schemas.appraisal_check_in import CheckInSummary
from app.services.appraisals.context import Caller


def _summary(check_in: AppraisalCheckIn, user_id: uuid.UUID, name: str) -> CheckInSummary:
    return CheckInSummary(
        id=check_in.id,
        user_id=user_id,
        person_name=name,
        period_start=check_in.period_start,
        period_end=check_in.period_end,
        status=check_in.status,
        closed=check_in.closed_at is not None,
        fact_count=len(check_in.fact_refs or []),
    )


async def my_check_ins(db: AsyncSession, caller: Caller) -> list[CheckInSummary]:
    """The caller's check-ins, newest first."""
    profile = await EmployeeProfileRepository(db, org_id=caller.org_id).get_by_user(caller.user_id)
    if profile is None:
        return []
    rows = await AppraisalCheckInRepository(db, org_id=caller.org_id).for_profiles([profile.id])
    return [_summary(c, caller.user_id, "") for c in rows]


async def team_check_ins(db: AsyncSession, caller: Caller) -> list[CheckInSummary]:
    """Each direct report's most recent check-in."""
    report_ids = await AppraisalRepository(db, org_id=caller.org_id).report_profile_ids(
        caller.user_id
    )
    profiles = await AppraisalRepository(db, org_id=caller.org_id).profiles_by_id(report_ids)
    users = {
        u.id: u
        for u in await UserRepository(db).get_many_by_ids([p.user_id for p in profiles.values()])
    }
    latest = await AppraisalCheckInRepository(db, org_id=caller.org_id).latest_for_profiles(
        list(profiles)
    )
    out = []
    for check_in in latest:
        profile = profiles[check_in.profile_id]
        user = users.get(profile.user_id)
        out.append(_summary(check_in, profile.user_id, user.name if user else ""))
    return sorted(out, key=lambda s: s.person_name.lower())
