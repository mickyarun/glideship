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


"""The manager's team list of feedback items."""

import uuid
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_enums import CheckInStatus
from app.repositories.appraisal import AppraisalRepository
from app.repositories.appraisal_check_in import AppraisalCheckInRepository
from app.repositories.appraisal_feedback import AppraisalFeedbackRepository
from app.repositories.user import UserRepository
from app.schemas.appraisal_feedback import FeedbackRow
from app.services.appraisals.context import Caller
from app.services.appraisals.feedback_read import in_period, is_overdue
from app.services.appraisals.org_clock import org_today


async def team_feedback(db: AsyncSession, caller: Caller) -> list[FeedbackRow]:
    """The items the caller holds for people who still report to them, newest first.

    A finished item stays with the manager who wrote it, but once the
    person has moved on it no longer shows in that manager's list.
    """
    repo = AppraisalRepository(db, org_id=caller.org_id)
    reports = set(await repo.report_profile_ids(caller.user_id))
    items = [
        i
        for i in await AppraisalFeedbackRepository(db, org_id=caller.org_id).for_manager(
            caller.user_id
        )
        if i.profile_id in reports
    ]
    profiles = await repo.profiles_by_id(list({i.profile_id for i in items}))
    names = {
        u.id: u.name
        for u in await UserRepository(db).get_many_by_ids([p.user_id for p in profiles.values()])
    }
    by_person: dict[uuid.UUID, list[AppraisalCheckIn]] = defaultdict(list)
    for check_in in await AppraisalCheckInRepository(db, org_id=caller.org_id).for_profiles(
        list(profiles)
    ):
        by_person[check_in.profile_id].append(check_in)
    today = await org_today(db, caller.org_id)
    rows = []
    for item in items:
        profile = profiles.get(item.profile_id)
        if profile is None:
            continue
        covered = [c for c in by_person[item.profile_id] if in_period(c, item)]
        rows.append(
            FeedbackRow(
                id=item.id,
                profile_id=item.profile_id,
                person_name=names.get(profile.user_id, ""),
                period_start=item.period_start,
                period_end=item.period_end,
                cadence=item.cadence,
                due_on=item.due_on,
                status=item.status,
                overdue=is_overdue(item, today),
                check_ins=len(covered),
                check_ins_added=sum(c.status is CheckInStatus.EMPLOYEE_ADDED for c in covered),
            )
        )
    return rows
