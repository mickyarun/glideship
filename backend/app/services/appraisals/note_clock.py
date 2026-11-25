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

"""Starting a manager note's clock: its due date, once there is something to answer.

A note is due ``feedback_due_days`` working days (on the manager's
calendar) after the check-in it answers is sent. If that check-in closes
unsent (the next one opens), the clock starts from the close instead, so
no note waits undated for ever. Sending a check-in starts the clock at
once (:func:`start_on_send`); each tick dates every note still waiting
(:func:`date_waiting_notes`), which also catches a send that crossed the
tick opening the note. A clock never starts before its note opened, so
nobody is handed a note that is already late.
"""

from datetime import date, tzinfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_cycle import AppraisalCycle
from app.repositories.appraisal_cycle import AppraisalCycleRepository
from app.repositories.appraisal_feedback import AppraisalFeedbackRepository
from app.repositories.appraisal_note_clock import AppraisalNoteClockRepository
from app.services.appraisals.due_dates import note_due
from app.services.appraisals.org_clock import org_today
from app.services.appraisals.work_calendar import load_calendars


async def start_on_send(db: AsyncSession, check_in: AppraisalCheckIn) -> None:
    """Date the note answering this just-sent check-in, if it is open and undated."""
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


async def date_waiting_notes(
    db: AsyncSession, cycle: AppraisalCycle, today: date, zone: tzinfo
) -> int:
    """Date every note in the cycle whose check-in was sent or closed; how many.

    Days are the org's own (``zone``), as everywhere else in appraisals.
    """
    waiting = await AppraisalNoteClockRepository(db, org_id=cycle.org_id).ready_to_date(cycle.id)
    if not waiting:
        return 0
    managers = {item.manager_user_id for item, _, _ in waiting}
    calendars = await load_calendars(db, cycle.org_id, managers, today)
    for item, answered_at, opened_at in waiting:
        start = max(answered_at.astimezone(zone).date(), opened_at.astimezone(zone).date())
        item.due_on = note_due(start, cycle.feedback_due_days, calendars.of(item.manager_user_id))
    await db.flush()
    return len(waiting)
