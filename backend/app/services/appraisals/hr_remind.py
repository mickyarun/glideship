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
manager with a note past its due date and not sent, gets the same words
the scheduled late reminder uses. People HR can't see (HR's own record,
their own manager's) are left out, as on the cycle page. Once a day per
cycle, recorded on the cycle, so the page can say when it last went out.
"""

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import CheckInCadence
from app.repositories.appraisal_check_in_due import AppraisalCheckInDueRepository
from app.repositories.appraisal_feedback import AppraisalFeedbackRepository
from app.schemas.appraisal_progress import RemindResult
from app.services.appraisals import reminder_text
from app.services.appraisals.context import Caller
from app.services.appraisals.errors import AppraisalConflictError
from app.services.appraisals.feedback_read import is_overdue
from app.services.appraisals.hr_scope import hidden_users
from app.services.appraisals.org_clock import org_today
from app.services.appraisals.reminders import Moment
from app.services.notifications import NotificationCategory
from app.services.slack_dm import send_each


async def _texts(db: AsyncSession, caller: Caller, cycle: AppraisalCycle) -> dict[uuid.UUID, str]:
    today = await org_today(db, cycle.org_id)
    hidden = await hidden_users(db, caller)
    base = settings.frontend_url
    lines: dict[uuid.UUID, list[str]] = defaultdict(list)
    check_ins = await AppraisalCheckInDueRepository(db, org_id=cycle.org_id).unsent(
        [cycle.id], today, announced_only=False
    )
    for c in sorted(check_ins, key=lambda c: c.period_start):
        if c.due_on < today and c.user_id not in hidden:
            lines[c.user_id].append(
                reminder_text.check_in_due_line(Moment.AFTER, c.period_start, c.due_on)
            )
    texts = {user: reminder_text.check_in_due_text(text, base) for user, text in lines.items()}
    notes = await AppraisalFeedbackRepository(db, org_id=cycle.org_id).for_cycles([cycle.id])
    late = [i for i in notes if is_overdue(i, today) and i.manager_user_id not in hidden]
    groups: dict[uuid.UUID, dict[tuple[date, CheckInCadence, date], int]] = defaultdict(
        lambda: defaultdict(int)
    )
    for item in late:
        if item.due_on is not None:
            groups[item.manager_user_id][(item.period_start, item.cadence, item.due_on)] += 1
    for manager, batches in groups.items():
        manager_lines = [
            reminder_text.feedback_line(
                Moment.AFTER,
                reminder_text.FeedbackBatch(start, cadence, due, total=count, done=0),
            )
            for (start, cadence, due), count in sorted(batches.items())
        ]
        texts[manager] = reminder_text.feedback_text(manager_lines, base)
    return texts


async def remind_late(db: AsyncSession, caller: Caller, cycle: AppraisalCycle) -> RemindResult:
    """Message everyone late in the cycle now; once a day."""
    today = await org_today(db, cycle.org_id)
    last = cycle.hr_reminded_at
    if last is not None and last.date() >= today:
        raise AppraisalConflictError("Reminders already went out today.")
    texts = await _texts(db, caller, cycle)
    reached = await send_each(cycle.org_id, NotificationCategory.APPRAISAL_REMINDERS, texts)
    cycle.hr_reminded_at = datetime.now(UTC)
    await db.flush()
    return RemindResult(people=len(texts), reached=sum(reached.values()))
