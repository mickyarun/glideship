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

"""Who's done and who's overdue in a running cycle: counts and states, no content.

HR's own appraisal and their own manager's are left out, rows and totals
alike, because HR rights never reach either (see :mod:`.access`).
Withdrawn people keep their row but their unwritten feedback is no longer
counted as overdue: it can't be written any more.
"""

import uuid
from collections import Counter, defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import AppraisalStatus, CheckInStatus, FeedbackStatus
from app.models.appraisal_manager_feedback import AppraisalManagerFeedback
from app.repositories.appraisal import AppraisalRepository
from app.repositories.appraisal_check_in import AppraisalCheckInRepository
from app.repositories.appraisal_feedback import AppraisalFeedbackRepository
from app.repositories.user import UserRepository
from app.schemas.appraisal_cycle import CycleProgress, ManagerOverdue, ProgressRow
from app.services.appraisals.context import Caller
from app.services.appraisals.feedback_read import is_overdue
from app.services.appraisals.hr_scope import hidden_users
from app.services.appraisals.org_clock import org_today


async def cycle_progress(db: AsyncSession, caller: Caller, cycle: AppraisalCycle) -> CycleProgress:
    """Each enrolled person's check-ins and feedback, and managers with overdue items."""
    org_id = cycle.org_id
    repo = AppraisalRepository(db, org_id=org_id)
    hidden = await hidden_users(db, caller)
    everyone = await repo.for_cycle(cycle.id)
    profiles = {
        pid: p
        for pid, p in (await repo.profiles_by_id([a.profile_id for a in everyone])).items()
        if p.user_id not in hidden
    }
    appraisals = [a for a in everyone if a.profile_id in profiles]
    withdrawn = {a.profile_id for a in appraisals if a.status is AppraisalStatus.WITHDRAWN}
    check_ins: dict[uuid.UUID, list[AppraisalCheckIn]] = defaultdict(list)
    for check_in in await AppraisalCheckInRepository(db, org_id=org_id).for_cycle(cycle.id):
        check_ins[check_in.profile_id].append(check_in)
    feedback: dict[uuid.UUID, list[AppraisalManagerFeedback]] = defaultdict(list)
    items = [
        i
        for i in await AppraisalFeedbackRepository(db, org_id=org_id).for_cycles([cycle.id])
        if i.profile_id in profiles
    ]
    for item in items:
        feedback[item.profile_id].append(item)
    user_ids = {p.user_id for p in profiles.values()} | {a.manager_user_id for a in appraisals}
    user_ids |= {i.manager_user_id for i in items}
    names = {u.id: u.name for u in await UserRepository(db).get_many_by_ids(list(user_ids))}
    today = await org_today(db, org_id)

    def late(item: AppraisalManagerFeedback) -> bool:
        return item.profile_id not in withdrawn and is_overdue(item, today)

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
                feedback_overdue=sum(late(i) for i in theirs),
            )
        )
    overdue = Counter(i.manager_user_id for i in items if late(i))
    return CycleProgress(
        people=sorted(rows, key=lambda r: r.name.lower()),
        feedback=len(items),
        feedback_done=sum(i.status is FeedbackStatus.DONE for i in items),
        managers_overdue=[
            ManagerOverdue(name=names.get(user_id, ""), overdue=count)
            for user_id, count in overdue.most_common()
        ],
    )
