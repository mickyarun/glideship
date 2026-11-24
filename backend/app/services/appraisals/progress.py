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

"""Who's done and who's late in a running cycle: counts and states, no content.

HR's own appraisal and their own manager's are left out, rows and totals
alike, because HR rights never reach either (see :mod:`.access`).
Withdrawn people and leavers keep their row, but nothing of theirs counts
as late (see :mod:`.cycle_people`), the same rule HR's reminder uses, as
are goals still short after the cycle's goals date. A check-in's state is
what anyone but the person may know (:func:`.team_overview.month_state`).
"""

import uuid
from collections import Counter, defaultdict
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import FeedbackStatus, GoalStatus
from app.models.appraisal_manager_feedback import AppraisalManagerFeedback
from app.repositories.appraisal import AppraisalRepository
from app.repositories.appraisal_check_in import AppraisalCheckInRepository
from app.repositories.appraisal_feedback import AppraisalFeedbackRepository
from app.repositories.appraisal_goal import AppraisalGoalRepository
from app.repositories.user import UserRepository
from app.schemas.appraisal_progress import CycleProgress, ManagerOverdue, ProgressRow
from app.services.appraisals.context import Caller
from app.services.appraisals.cycle_people import late_on_goals, not_chased
from app.services.appraisals.feedback_read import is_overdue
from app.services.appraisals.hr_scope import hidden_users
from app.services.appraisals.org_clock import org_today
from app.services.appraisals.progress_periods import check_in_periods, note_periods, slices_of
from app.services.appraisals.settings import goal_floor
from app.services.appraisals.team_overview import month_state


async def cycle_progress(db: AsyncSession, caller: Caller, cycle: AppraisalCycle) -> CycleProgress:
    """Each enrolled person's goals, check-ins and notes, with totals per period."""
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
    check_ins: dict[uuid.UUID, dict[date, AppraisalCheckIn]] = defaultdict(dict)
    for check_in in await AppraisalCheckInRepository(db, org_id=org_id).for_cycle(cycle.id):
        if check_in.profile_id in profiles:
            check_ins[check_in.profile_id][check_in.period_start] = check_in
    feedback: dict[uuid.UUID, list[AppraisalManagerFeedback]] = defaultdict(list)
    items = [
        i
        for i in await AppraisalFeedbackRepository(db, org_id=org_id).for_cycles([cycle.id])
        if i.profile_id in profiles
    ]
    for item in items:
        feedback[item.profile_id].append(item)
    goals = await AppraisalGoalRepository(db, org_id=org_id).status_counts(list(profiles))
    user_ids = {p.user_id for p in profiles.values()} | {a.manager_user_id for a in appraisals}
    user_ids |= {i.manager_user_id for i in items}
    names = {u.id: u.name for u in await UserRepository(db).get_many_by_ids(list(user_ids))}
    today = await org_today(db, org_id)
    quiet = not_chased(appraisals, profiles, today)
    floor = await goal_floor(db, org_id)
    accepted = {
        pid: goals.get((pid, cycle.period_start, GoalStatus.ACCEPTED), 0) for pid in profiles
    }
    short = late_on_goals(appraisals, accepted, cycle, floor, today, quiet)
    periods = slices_of(cycle)

    def late(item: AppraisalManagerFeedback) -> bool:
        return item.profile_id not in quiet and is_overdue(item, today)

    rows = []
    for appraisal in appraisals:
        profile = profiles[appraisal.profile_id]
        mine, theirs = check_ins[profile.id], feedback[profile.id]
        states = [month_state(mine.get(start), today) for start, _ in periods]
        rows.append(
            ProgressRow(
                user_id=profile.user_id,
                name=names.get(profile.user_id, ""),
                manager_user_id=appraisal.manager_user_id,
                manager_name=names.get(appraisal.manager_user_id, ""),
                status=appraisal.status,
                goals_accepted=accepted[profile.id],
                goals_late=profile.id in short,
                months=states,
                check_ins=len(mine),
                check_ins_added=states.count("sent"),
                check_ins_missed=states.count("missed"),
                check_ins_late=0 if profile.id in quiet else states.count("late"),
                feedback=len(theirs),
                feedback_done=sum(i.status is FeedbackStatus.DONE for i in theirs),
                feedback_overdue=sum(late(i) for i in theirs),
                feedback_due=sum(i.due_on is not None for i in theirs),
                quiet=profile.id in quiet,
            )
        )
    overdue = Counter(i.manager_user_id for i in items if late(i))
    live = [check_ins[a.profile_id] for a in appraisals if a.profile_id not in quiet]
    late_people = {r.user_id for r in rows if r.check_ins_late}
    late_people |= {a.manager_user_id for a in appraisals if a.profile_id in short}
    return CycleProgress(
        people=sorted(rows, key=lambda r: r.name.lower()),
        feedback=len(items),
        feedback_done=sum(i.status is FeedbackStatus.DONE for i in items),
        managers_overdue=[
            ManagerOverdue(user_id=user_id, name=names.get(user_id, ""), overdue=count)
            for user_id, count in overdue.most_common()
        ],
        min_goals=floor,
        check_in_periods=check_in_periods(periods, live),
        note_periods=note_periods([i for i in items if i.profile_id not in quiet]),
        remind_count=len(late_people | set(overdue)),
        reminded_at=cycle.hr_reminded_at,
        reminded_today=cycle.hr_reminded_at is not None
        and await org_today(db, org_id, now=cycle.hr_reminded_at) == today,
    )
