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

"""Who's done and who's overdue in a running cycle: counts and states, no content."""

import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import CheckInStatus, FeedbackStatus
from app.models.appraisal_manager_feedback import AppraisalManagerFeedback
from app.repositories.appraisal import AppraisalRepository
from app.repositories.appraisal_check_in import AppraisalCheckInRepository
from app.repositories.appraisal_feedback import AppraisalFeedbackRepository
from app.repositories.user import UserRepository
from app.schemas.appraisal_cycle import CycleProgress, ManagerOverdue, ProgressRow
from app.services.appraisals.feedback_read import is_overdue


async def cycle_progress(db: AsyncSession, cycle: AppraisalCycle) -> CycleProgress:
    """Each enrolled person's check-ins and feedback, and managers with overdue items."""
    org_id = cycle.org_id
    repo = AppraisalRepository(db, org_id=org_id)
    appraisals = await repo.for_cycle(cycle.id)
    profiles = await repo.profiles_by_id([a.profile_id for a in appraisals])
    check_ins: dict[uuid.UUID, list[AppraisalCheckIn]] = defaultdict(list)
    for check_in in await AppraisalCheckInRepository(db, org_id=org_id).for_cycle(cycle.id):
        check_ins[check_in.profile_id].append(check_in)
    feedback: dict[uuid.UUID, list[AppraisalManagerFeedback]] = defaultdict(list)
    items = await AppraisalFeedbackRepository(db, org_id=org_id).for_cycles([cycle.id])
    for item in items:
        feedback[item.profile_id].append(item)
    user_ids = {p.user_id for p in profiles.values()} | {a.manager_user_id for a in appraisals}
    user_ids |= {i.manager_user_id for i in items}
    names = {u.id: u.name for u in await UserRepository(db).get_many_by_ids(list(user_ids))}
    today = datetime.now(UTC).date()
    rows = []
    for appraisal in appraisals:
        profile = profiles.get(appraisal.profile_id)
        if profile is None:
            continue
        mine, theirs = check_ins[profile.id], feedback[profile.id]
        rows.append(
            ProgressRow(
                user_id=profile.user_id,
                name=names.get(profile.user_id, ""),
                manager_name=names.get(appraisal.manager_user_id, ""),
                status=appraisal.status,
                check_ins=len(mine),
                check_ins_added=sum(c.status is CheckInStatus.EMPLOYEE_ADDED for c in mine),
                check_ins_missed=sum(c.status is CheckInStatus.MISSED for c in mine),
                feedback=len(theirs),
                feedback_done=sum(i.status is FeedbackStatus.DONE for i in theirs),
                feedback_overdue=sum(is_overdue(i, today) for i in theirs),
            )
        )
    late = Counter(i.manager_user_id for i in items if is_overdue(i, today))
    return CycleProgress(
        people=sorted(rows, key=lambda r: r.name.lower()),
        feedback=len(items),
        feedback_done=sum(i.status is FeedbackStatus.DONE for i in items),
        managers_overdue=[
            ManagerOverdue(name=names.get(user_id, ""), overdue=count)
            for user_id, count in late.most_common()
        ],
    )
