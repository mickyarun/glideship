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

"""Sending a check-in: from then on the manager and HR read what it says.

Only the person sends their own, while it is open, once. Sending starts
the clock on the manager's note that answers it: the note covering this
check-in's period end is due ``feedback_due_days`` working days later,
on the manager's calendar. A note that opens after the send gets its due
date when it opens (:mod:`.feedback_open`).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_check_in import AppraisalCheckIn
from app.repositories.appraisal_cycle import AppraisalCycleRepository
from app.repositories.appraisal_feedback import AppraisalFeedbackRepository
from app.services.appraisals.context import CheckInContext
from app.services.appraisals.due_dates import note_due
from app.services.appraisals.errors import AppraisalConflictError
from app.services.appraisals.org_clock import org_today
from app.services.appraisals.work_calendar import load_calendars


async def send_check_in(db: AsyncSession, ctx: CheckInContext, actor_id: uuid.UUID) -> None:
    """Send the caller's own open check-in."""
    check_in = ctx.check_in
    if not (ctx.is_open and ctx.profile.user_id == actor_id):
        raise AppraisalConflictError("Only the person can send their open check-in.")
    if check_in.sent_at is not None:
        raise AppraisalConflictError("This check-in was already sent.")
    check_in.sent_at = datetime.now(UTC)
    await start_note_clock(db, check_in)
    await db.flush()


async def start_note_clock(db: AsyncSession, check_in: AppraisalCheckIn) -> None:
    """Give the note answering this sent check-in its due date, if it has none yet.

    Only the note whose period ends with this check-in's: a quarterly note
    waits for the quarter's last check-in.
    """
    org_id = check_in.org_id
    item = await AppraisalFeedbackRepository(db, org_id=org_id).covering(
        check_in.cycle_id, check_in.profile_id, check_in.period_end
    )
    cycle = await AppraisalCycleRepository(db, org_id=org_id).get_by_id(check_in.cycle_id)
    if item is None or cycle is None or item.due_on is not None:
        return
    today = await org_today(db, org_id)
    calendars = await load_calendars(db, org_id, {item.manager_user_id}, today)
    item.due_on = note_due(today, cycle.feedback_due_days, calendars.of(item.manager_user_id))
