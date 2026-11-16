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

"""Today's reminders for the review steps, for one org (reads only).

The employee's self-review (open, then due), the manager's reviews (one
message per manager per cycle, covering everyone waiting), and the
employee's shared result to read and acknowledge. Each announces its
step once, recorded on the appraisal, and repeats on the cycle's
reminder offsets until the step is done.
"""

import uuid
from collections import defaultdict
from collections.abc import Callable
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.appraisal import Appraisal
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import AppraisalStatus
from app.models.digest_claim import DigestClaimKind
from app.repositories.appraisal import AppraisalRepository, NotifiedColumn
from app.repositories.employee_reporting_manager import EmployeeReportingManagerRepository
from app.services.appraisals import review_reminder_text as words
from app.services.appraisals.reminder_message import Message, Outbox
from app.services.appraisals.reminders import Moment, Schedule, moment
from app.services.appraisals.work_calendar import Calendars, load_calendars

SELF = DigestClaimKind.APPRAISAL_SELF_DUE
REVIEW = DigestClaimKind.APPRAISAL_REVIEW_DUE
RESULT = DigestClaimKind.APPRAISAL_ACK_DUE
# Which appraisal column each stream's announcement is recorded in.
NOTIFIED: dict[DigestClaimKind, NotifiedColumn] = {
    SELF: "self_notified_at",
    REVIEW: "review_notified_at",
    RESULT: "result_notified_at",
}


def _employee_stream(
    appraisals: list[Appraisal],
    users: dict[uuid.UUID, uuid.UUID],
    cycles: dict[uuid.UUID, AppraisalCycle],
    calendars: Calendars,
    day: date,
    skip: set[uuid.UUID],
    step: tuple[AppraisalStatus, str, Callable[[AppraisalCycle], date]],
    text: Callable[[Moment, str, date, str], str],
) -> Outbox:
    """One message per employee whose appraisal is at this step."""
    status, notified, due_of = step
    outbox: Outbox = {}
    for appraisal in appraisals:
        user = users.get(appraisal.profile_id)
        if appraisal.status is not status or user is None or user in skip:
            continue
        cycle = cycles[appraisal.cycle_id]
        due = due_of(cycle)
        announced = getattr(appraisal, notified) is not None
        when = moment(day, announced, due, Schedule.of(cycle), calendars.of(user))
        if when is not None:
            message = text(when, cycle.name, due, settings.frontend_url)
            outbox[user] = Message(message, appraisals=[] if announced else [appraisal.id])
    return outbox


async def _managers(
    db: AsyncSession,
    org_id: uuid.UUID,
    appraisals: list[Appraisal],
    cycles: dict[uuid.UUID, AppraisalCycle],
    calendars: Calendars,
    day: date,
    skip: set[uuid.UUID],
) -> Outbox:
    """One message per manager: every cycle with reviews waiting for them."""
    links = await EmployeeReportingManagerRepository(db, org_id=org_id).list_for_profiles(
        list({a.profile_id for a in appraisals})
    )
    managing = {(pid, m.user_id) for pid, ms in links.items() for m in ms if m.is_active}
    groups: dict[tuple[uuid.UUID, uuid.UUID], list[Appraisal]] = defaultdict(list)
    for a in appraisals:
        if (a.profile_id, a.manager_user_id) in managing:
            groups[(a.manager_user_id, a.cycle_id)].append(a)
    lines: dict[uuid.UUID, list[str]] = defaultdict(list)
    announces: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    for (manager, cycle_id), group in groups.items():
        waiting = [a for a in group if a.status is AppraisalStatus.MANAGER_REVIEW]
        if manager in skip or not waiting:
            continue
        cycle = cycles[cycle_id]
        fresh = [a.id for a in waiting if a.review_notified_at is None]
        when = moment(day, not fresh, cycle.manager_due, Schedule.of(cycle), calendars.of(manager))
        if when is None:
            continue
        lines[manager].append(
            words.review_text(
                when,
                cycle.name,
                cycle.manager_due,
                len(waiting),
                len(group),
                settings.frontend_url,
            )
        )
        announces[manager].extend(fresh)
    return {m: Message("\n".join(text), appraisals=announces[m]) for m, text in lines.items()}


async def review_streams(
    db: AsyncSession,
    org_id: uuid.UUID,
    cycles: list[AppraisalCycle],
    day: date,
    skip: dict[DigestClaimKind, set[uuid.UUID]],
) -> dict[DigestClaimKind, Outbox]:
    """The three review-step outboxes by claim kind; ``skip`` as in ``compose_day``."""
    repo = AppraisalRepository(db, org_id=org_id)
    by_id = {c.id: c for c in cycles}
    appraisals = await repo.live_in_cycles(list(by_id))
    if not appraisals:
        return {}
    profiles = await repo.profiles_by_id(list({a.profile_id for a in appraisals}))
    users = {pid: p.user_id for pid, p in profiles.items()}
    people = set(users.values()) | {a.manager_user_id for a in appraisals}
    calendars = await load_calendars(db, org_id, people, day)
    common = (appraisals, users, by_id, calendars, day)
    return {
        SELF: _employee_stream(
            *common,
            skip.get(SELF, set()),
            (AppraisalStatus.SELF_REVIEW, "self_notified_at", lambda c: c.self_due),
            words.self_text,
        ),
        REVIEW: await _managers(
            db, org_id, appraisals, by_id, calendars, day, skip.get(REVIEW, set())
        ),
        RESULT: _employee_stream(
            *common,
            skip.get(RESULT, set()),
            (AppraisalStatus.SHARED, "result_notified_at", lambda c: c.ack_due),
            words.result_text,
        ),
    }
