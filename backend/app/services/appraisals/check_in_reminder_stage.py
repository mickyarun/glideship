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

"""Today's check-in reminders, for one org (reads only): ready, then due.

Each person with an open check-in they haven't sent hears about it two
working days before it is due, on the day, and once the working day after
when it is late, counted on their own calendar. Opening is announced by
the "ready" message, so this stream never announces. Sending it stops
the reminders. One message per person covers every check-in due that day.
"""

import uuid
from collections import defaultdict
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.appraisal_cycle import AppraisalCycle
from app.repositories.appraisal import AppraisalRepository
from app.repositories.appraisal_check_in import AppraisalCheckInRepository
from app.repositories.appraisal_check_in_due import AppraisalCheckInDueRepository
from app.services.appraisals import reminder_text
from app.services.appraisals.reminder_message import Message, Outbox
from app.services.appraisals.reminders import CHECK_IN_SCHEDULE, moment
from app.services.appraisals.work_calendar import load_calendars


async def check_in_due_stream(
    db: AsyncSession,
    org_id: uuid.UUID,
    cycles: list[AppraisalCycle],
    day: date,
    skip: set[uuid.UUID],
) -> Outbox:
    """Each person's check-in reminder today; ``skip`` holds people already reached."""
    waiting = await AppraisalCheckInDueRepository(db, org_id=org_id).unsent([c.id for c in cycles])
    waiting = [w for w in waiting if w.user_id not in skip]
    if not waiting:
        return {}
    calendars = await load_calendars(db, org_id, {w.user_id for w in waiting}, day)
    lines: dict[uuid.UUID, list[str]] = defaultdict(list)
    for check_in in sorted(waiting, key=lambda w: w.period_start):
        when = moment(
            day, True, check_in.due_on, CHECK_IN_SCHEDULE, calendars.of(check_in.user_id)
        )
        if when is not None:
            lines[check_in.user_id].append(
                reminder_text.check_in_due_line(when, check_in.period_start, check_in.due_on)
            )
    base = settings.frontend_url
    return {
        user: Message(reminder_text.check_in_due_text(text, base)) for user, text in lines.items()
    }


async def ready_stream(
    db: AsyncSession, org_id: uuid.UUID, cycles: list[AppraisalCycle], skip: set[uuid.UUID]
) -> Outbox:
    """Each person's "your check-in is ready" message, for check-ins not yet announced."""
    waiting = await AppraisalCheckInRepository(db, org_id=org_id).unannounced(
        [c.id for c in cycles]
    )
    profiles = await AppraisalRepository(db, org_id=org_id).profiles_by_id(
        list({c.profile_id for c in waiting})
    )
    labels: dict[uuid.UUID, list[str]] = defaultdict(list)
    ids: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    for check_in in sorted(waiting, key=lambda c: c.period_start):
        profile = profiles.get(check_in.profile_id)
        if profile is None or profile.user_id in skip:
            continue
        labels[profile.user_id].append(f"{check_in.period_start:%B}")
        ids[profile.user_id].append(check_in.id)
    base = settings.frontend_url
    return {
        user: Message(reminder_text.check_in_ready_text(names, base), check_ins=ids[user])
        for user, names in labels.items()
    }
