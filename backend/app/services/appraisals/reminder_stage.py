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

One stream per claim kind: "your check-in is ready" on the first pass
after it opens; one feedback reminder per manager covering all their
reports and periods; HR's overdue list; and the review steps
(:mod:`.review_reminder_stage`). Each message records which
check-ins and items it announces, so the opening line is sent exactly
once even when an item opens after the day's reminder went out. People
already reached today are skipped before anything is composed for them.
Days are counted on the recipient's calendar; HR's list goes to everyone
holding ``appraisals:manage`` and is counted on the org's default one.
"""

import uuid
from collections import Counter, defaultdict
from collections.abc import Collection
from datetime import date

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
from app.repositories.employee_reporting_manager import EmployeeReportingManagerRepository
from app.repositories.user import UserRepository
from app.services.appraisals import reminder_text
from app.services.appraisals.reminder_message import Message, Outbox
from app.services.appraisals.reminders import Schedule, hr_list_today, moment
from app.services.appraisals.review_reminder_stage import review_streams
from app.services.appraisals.work_calendar import load_calendars
from app.services.notifications import NotificationCategory, category_default

GroupKey = tuple[uuid.UUID, uuid.UUID, date]
READY = DigestClaimKind.APPRAISAL_CHECK_IN_READY
FEEDBACK = DigestClaimKind.APPRAISAL_FEEDBACK_DUE
HR_LIST = DigestClaimKind.APPRAISAL_HR_OVERDUE


async def _ready(
    db: AsyncSession, org_id: uuid.UUID, cycles: list[AppraisalCycle], skip: set[uuid.UUID]
) -> Outbox:
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


async def _still_managing(
    db: AsyncSession, org_id: uuid.UUID, items: list[AppraisalManagerFeedback]
) -> set[tuple[uuid.UUID, uuid.UUID]]:
    """(profile, manager) pairs where the manager is still an active manager."""
    links = await EmployeeReportingManagerRepository(db, org_id=org_id).list_for_profiles(
        list({i.profile_id for i in items})
    )
    return {(pid, m.user_id) for pid, ms in links.items() for m in ms if m.is_active}


def _groups(
    items: Collection[AppraisalManagerFeedback],
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
    skip: set[uuid.UUID],
) -> tuple[Outbox, Counter[uuid.UUID]]:
    """Each manager's feedback reminder, and who is on HR's overdue list.

    An item whose manager has left the person's reporting line can't be
    written by them, so it is left out of their reminder; HR still sees it.
    """
    items = await AppraisalFeedbackRepository(db, org_id=org_id).with_open_items(list(cycles))
    managing = await _still_managing(db, org_id, items)
    groups = _groups(items)
    calendars = await load_calendars(db, org_id, {k[0] for k in groups} - skip, day)
    lines: dict[uuid.UUID, list[str]] = defaultdict(list)
    announces: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    overdue: Counter[uuid.UUID] = Counter()
    for (manager, cycle_id, _), group in sorted(groups.items(), key=lambda g: g[0][2]):
        schedule, first = Schedule.of(cycles[cycle_id]), group[0]
        still_open = [i for i in group if i.status is FeedbackStatus.OPEN]
        if hr_list_today(day, first.due_on, schedule, calendars.default):
            overdue[manager] += len(still_open)
        mine = [i for i in group if (i.profile_id, manager) in managing]
        waiting = [i for i in mine if i.status is FeedbackStatus.OPEN]
        if manager in skip or not waiting:
            continue
        unannounced = [i.id for i in waiting if i.notified_at is None]
        when = moment(day, not unannounced, first.due_on, schedule, calendars.of(manager))
        if when is None:
            continue
        batch = reminder_text.FeedbackBatch(
            period_start=first.period_start,
            cadence=first.cadence,
            due_on=first.due_on,
            total=len(mine),
            done=len(mine) - len(waiting),
        )
        lines[manager].append(reminder_text.feedback_line(when, batch))
        announces[manager].extend(unannounced)
    base = settings.frontend_url
    outbox = {
        m: Message(reminder_text.feedback_text(text, base), feedback=announces[m])
        for m, text in lines.items()
    }
    return outbox, overdue


async def _hr(
    db: AsyncSession, org_id: uuid.UUID, overdue: Counter[uuid.UUID], skip: set[uuid.UUID]
) -> Outbox:
    late = +overdue
    if not late:
        return {}
    users = UserRepository(db)
    names = {u.id: u.name for u in await users.get_many_by_ids(list(late))}
    text = reminder_text.hr_overdue_text(
        [(names.get(manager, ""), count) for manager, count in late.most_common()],
        settings.frontend_url,
    )
    category = NotificationCategory.APPRAISAL_REMINDERS
    hr = await users.list_slack_recipients(
        org_id,
        category=category,
        default_enabled=category_default(category),
        permission=APPRAISALS_MANAGE,
    )
    return {user_id: Message(text) for user_id, _ in hr if user_id not in skip}


async def compose_day(
    db: AsyncSession, org_id: uuid.UUID, day: date, skip: dict[DigestClaimKind, set[uuid.UUID]]
) -> dict[DigestClaimKind, Outbox]:
    """Every reminder due today in the org's running cycles, by claim kind.

    ``skip`` holds, per kind, people already reached today.
    """
    cycles = await AppraisalCycleRepository(db, org_id=org_id).running()
    if not cycles:
        return {}
    by_id = {c.id: c for c in cycles}
    feedback, overdue = await _feedback(db, org_id, by_id, day, skip.get(FEEDBACK, set()))
    return {
        READY: await _ready(db, org_id, cycles, skip.get(READY, set())),
        FEEDBACK: feedback,
        HR_LIST: await _hr(db, org_id, overdue, skip.get(HR_LIST, set())),
        **await review_streams(db, org_id, cycles, day, skip),
    }
