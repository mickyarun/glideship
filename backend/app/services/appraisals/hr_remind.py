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

"""HR's manual "remind the late ones": one Slack message each, now.

Everyone with a check-in past its due date and not sent, and every
manager with a note past its due date and not sent, or with reports
still short of goals after the cycle's goals date, gets one message
saying what is late, worded as the scheduled reminders word it. The
people are the ones the cycle page counts: not HR's own record or their
manager's, and nobody withdrawn or gone
(:mod:`.cycle_people`). Once a day per running cycle in the org's time
zone, claimed on the cycle row before anything is sent.
"""

import uuid
from collections import Counter, defaultdict
from datetime import UTC, date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import CheckInCadence, GoalStatus
from app.repositories.appraisal import AppraisalRepository
from app.repositories.appraisal_check_in_due import AppraisalCheckInDueRepository
from app.repositories.appraisal_cycle import RUNNING
from app.repositories.appraisal_cycle_remind import AppraisalCycleRemindRepository
from app.repositories.appraisal_feedback import AppraisalFeedbackRepository
from app.repositories.appraisal_goal import AppraisalGoalRepository
from app.schemas.appraisal_progress import RemindResult
from app.services.appraisals import reminder_text
from app.services.appraisals.context import Caller
from app.services.appraisals.cycle_people import late_on_goals, not_chased
from app.services.appraisals.errors import AppraisalConflictError
from app.services.appraisals.feedback_read import is_overdue
from app.services.appraisals.hr_scope import hidden_users
from app.services.appraisals.org_clock import org_day_start, org_today
from app.services.appraisals.reminders import Moment
from app.services.appraisals.settings import goal_floor
from app.services.notifications import NotificationCategory
from app.services.slack_dm import send_each


async def _texts(db: AsyncSession, caller: Caller, cycle: AppraisalCycle) -> dict[uuid.UUID, str]:
    today = await org_today(db, cycle.org_id)
    hidden = await hidden_users(db, caller)
    base = settings.frontend_url
    parts: dict[uuid.UUID, list[str]] = defaultdict(list)
    lines: dict[uuid.UUID, list[str]] = defaultdict(list)
    check_ins = await AppraisalCheckInDueRepository(db, org_id=cycle.org_id).unsent(
        [cycle.id], today, announced_only=False
    )
    for c in sorted(check_ins, key=lambda c: c.period_start):
        if c.due_on < today and c.user_id not in hidden:
            lines[c.user_id].append(
                reminder_text.check_in_due_line(Moment.AFTER, c.period_start, c.due_on)
            )
    for user, text in lines.items():
        parts[user].append(reminder_text.check_in_due_text(text, base))
    repo = AppraisalRepository(db, org_id=cycle.org_id)
    appraisals = await repo.for_cycle(cycle.id)
    profiles = await repo.profiles_by_id([a.profile_id for a in appraisals])
    quiet = not_chased(appraisals, profiles, today)
    seen = {pid for pid, p in profiles.items() if p.user_id not in hidden and pid not in quiet}
    notes = await AppraisalFeedbackRepository(db, org_id=cycle.org_id).for_cycles([cycle.id])
    late = [i for i in notes if i.profile_id in seen and is_overdue(i, today)]
    groups: dict[uuid.UUID, dict[tuple[date, CheckInCadence, date], int]] = defaultdict(
        lambda: defaultdict(int)
    )
    for item in late:
        if item.due_on is not None:
            groups[item.manager_user_id][(item.period_start, item.cadence, item.due_on)] += 1
    manager_lines: dict[uuid.UUID, list[str]] = defaultdict(list)
    for manager, batches in groups.items():
        manager_lines[manager] += [
            reminder_text.feedback_line(
                Moment.AFTER,
                reminder_text.FeedbackBatch(start, cadence, due, total=count, done=0),
            )
            for (start, cadence, due), count in sorted(batches.items())
        ]
    counts = await AppraisalGoalRepository(db, org_id=cycle.org_id).status_counts(seen)
    accepted = {pid: counts.get((pid, cycle.period_start, GoalStatus.ACCEPTED), 0) for pid in seen}
    floor = await goal_floor(db, cycle.org_id)
    short = late_on_goals(
        [a for a in appraisals if a.profile_id in seen], accepted, cycle, floor, today, quiet
    )
    for manager, people in Counter(
        a.manager_user_id for a in appraisals if a.profile_id in short
    ).items():
        manager_lines[manager].append(reminder_text.goals_late_line(people, cycle.goals_due))
    for manager, text in manager_lines.items():
        parts[manager].append(reminder_text.feedback_text(text, base))
    return {user: "\n\n".join(texts) for user, texts in parts.items()}


async def remind_late(db: AsyncSession, caller: Caller, cycle: AppraisalCycle) -> RemindResult:
    """Message everyone late in the cycle now; once a day, and only while it runs.

    Nobody late: nothing is sent and the day isn't used up. Otherwise the
    day is claimed on the cycle row first, so two clicks can't both send.
    """
    if cycle.status not in RUNNING:
        raise AppraisalConflictError("Only a running cycle can send reminders.")
    texts = await _texts(db, caller, cycle)
    if not texts:
        return RemindResult(people=0, reached=0)
    claimed = await AppraisalCycleRemindRepository(db, org_id=cycle.org_id).claim_day(
        cycle.id, await org_day_start(db, cycle.org_id), datetime.now(UTC)
    )
    if not claimed:
        raise AppraisalConflictError("Reminders already went out today.")
    reached = await send_each(cycle.org_id, NotificationCategory.APPRAISAL_REMINDERS, texts)
    return RemindResult(people=len(texts), reached=sum(reached.values()))
