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

"""What each person's appraisal reminder says today, for one org (reads only).

Three streams in one place, each a claim kind: "your check-in is ready"
for the employee on the day it opens; one feedback reminder per manager
covering all their reports and periods; and HR's overdue list. Days are
counted on the recipient's calendar, except HR's list, which goes to
everyone holding ``appraisals:manage`` and is counted on the org's default
calendar.
"""

import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, tzinfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.permissions_people import APPRAISALS_MANAGE
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import FeedbackStatus
from app.models.appraisal_manager_feedback import AppraisalManagerFeedback
from app.models.digest_claim import DigestClaimKind
from app.repositories.appraisal import AppraisalRepository
from app.repositories.appraisal_check_in import AppraisalCheckInRepository
from app.repositories.appraisal_cycle import AppraisalCycleRepository
from app.repositories.appraisal_feedback import AppraisalFeedbackRepository
from app.repositories.user import UserRepository
from app.services.appraisals import reminder_text
from app.services.appraisals.reminders import Schedule, hr_list_today, moment
from app.services.appraisals.work_calendar import load_calendars
from app.services.notifications import NotificationCategory, category_default

Texts = dict[uuid.UUID, str]
GroupKey = tuple[uuid.UUID, uuid.UUID, date]


async def _ready(
    db: AsyncSession, org_id: uuid.UUID, cycles: list[AppraisalCycle], day: date, zone: tzinfo
) -> Texts:
    start = datetime.combine(day, time(), tzinfo=zone)
    opened = await AppraisalCheckInRepository(db, org_id=org_id).opened_between(
        [c.id for c in cycles], start, start + timedelta(days=1)
    )
    profiles = await AppraisalRepository(db, org_id=org_id).profiles_by_id(
        list({c.profile_id for c in opened})
    )
    labels: dict[uuid.UUID, list[str]] = defaultdict(list)
    for check_in in sorted(opened, key=lambda c: c.period_start):
        profile = profiles.get(check_in.profile_id)
        if profile is not None:
            labels[profile.user_id].append(f"{check_in.period_start:%B}")
    base = settings.frontend_url
    return {user: reminder_text.check_in_ready_text(names, base) for user, names in labels.items()}


def _groups(
    items: list[AppraisalManagerFeedback],
) -> dict[GroupKey, list[AppraisalManagerFeedback]]:
    """Items by (manager, cycle, period): one line in one manager's reminder."""
    groups: dict[GroupKey, list[AppraisalManagerFeedback]] = defaultdict(list)
    for item in items:
        groups[(item.manager_user_id, item.cycle_id, item.period_start)].append(item)
    return groups


async def _feedback(
    db: AsyncSession,
    org_id: uuid.UUID,
    cycles: dict[uuid.UUID, AppraisalCycle],
    day: date,
    zone: tzinfo,
) -> tuple[Texts, Counter[uuid.UUID]]:
    """Each manager's feedback reminder, and who is on HR's overdue list."""
    items = await AppraisalFeedbackRepository(db, org_id=org_id).for_cycles(list(cycles))
    groups = _groups(items)
    calendars = await load_calendars(db, org_id, {key[0] for key in groups}, day)
    lines: dict[uuid.UUID, list[str]] = defaultdict(list)
    overdue: Counter[uuid.UUID] = Counter()
    for (manager, cycle_id, _), group in sorted(groups.items(), key=lambda g: g[0][2]):
        still_open = [i for i in group if i.status is FeedbackStatus.OPEN]
        if not still_open:
            continue
        first, schedule = group[0], Schedule.of(cycles[cycle_id])
        opened_on = min(i.created_at.astimezone(zone).date() for i in group)
        when = moment(day, opened_on, first.due_on, schedule, calendars.of(manager))
        if when is not None:
            batch = reminder_text.FeedbackBatch(
                period_start=first.period_start,
                cadence=first.cadence,
                due_on=first.due_on,
                total=len(group),
                done=len(group) - len(still_open),
            )
            lines[manager].append(reminder_text.feedback_line(when, batch))
        if hr_list_today(day, first.due_on, schedule, calendars.default):
            overdue[manager] += len(still_open)
    base = settings.frontend_url
    return {m: reminder_text.feedback_text(text, base) for m, text in lines.items()}, overdue


async def _hr(db: AsyncSession, org_id: uuid.UUID, overdue: Counter[uuid.UUID]) -> Texts:
    if not overdue:
        return {}
    users = UserRepository(db)
    names = {u.id: u.name for u in await users.get_many_by_ids(list(overdue))}
    text = reminder_text.hr_overdue_text(
        [(names.get(manager, ""), count) for manager, count in overdue.most_common()],
        settings.frontend_url,
    )
    category = NotificationCategory.APPRAISAL_REMINDERS
    hr = await users.list_slack_recipients(
        org_id,
        category=category,
        default_enabled=category_default(category),
        permission=APPRAISALS_MANAGE,
    )
    return {user_id: text for user_id, _ in hr}


async def compose_day(
    db: AsyncSession, org_id: uuid.UUID, day: date, zone: tzinfo
) -> dict[DigestClaimKind, Texts]:
    """Every reminder due today in the org's running cycles, by claim kind."""
    cycles = await AppraisalCycleRepository(db, org_id=org_id).running()
    if not cycles:
        return {}
    feedback, overdue = await _feedback(db, org_id, {c.id: c for c in cycles}, day, zone)
    return {
        DigestClaimKind.APPRAISAL_CHECK_IN_READY: await _ready(db, org_id, cycles, day, zone),
        DigestClaimKind.APPRAISAL_FEEDBACK_DUE: feedback,
        DigestClaimKind.APPRAISAL_HR_OVERDUE: await _hr(db, org_id, overdue),
    }
