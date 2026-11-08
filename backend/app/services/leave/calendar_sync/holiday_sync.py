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
"""Put each person's public holidays on their Google Calendar as Out of office.

Reconciles like a request does: works out the events a person's upcoming
mandatory holidays should have (none when sync is off) and fixes whatever
we tagged ``holiday`` on their calendar from today on. Past holidays are
left as they were. Runs after HR saves the sync settings, changes a
policy's holidays, or moves people onto another policy.

One run per org at a time, each planned once it holds the lock, so an
older run can't put back a holiday a newer one took off. Best effort: one
person's calendar failing doesn't stop the rest.
"""

import uuid
from collections.abc import Collection
from dataclasses import dataclass
from datetime import date, datetime, time

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.leave_request import LeaveKind, LeaveStatus
from app.repositories.leave_calendar_people import LeaveCalendarPeopleRepository
from app.repositories.leave_policy import LeavePolicyRepository
from app.repositories.leave_request import LeaveRequestRepository
from app.services.google.calendar_api import Event
from app.services.leave.calendar_sync.events import HOLIDAY_TAG, holiday_events
from app.services.leave.calendar_sync.settings import CalendarSync, load_sync
from app.services.leave.calendar_sync.sync import (
    SYNC_ERRORS,
    apply_events,
    one_at_a_time,
    sync_request,
)
from app.services.leave.policies import ensure_default_policy, mandatory_holidays, today_for
from app.services.quiz_schedule_math import resolve_zone

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class _Plan:
    user_id: uuid.UUID
    email: str
    events: dict[str, Event]
    since: datetime


async def sync_holidays(
    org_id: uuid.UUID,
    *,
    policy_id: uuid.UUID | None = None,
    user_ids: Collection[uuid.UUID] | None = None,
) -> None:
    """Bring people's holiday events in line: everyone, one policy's, or some people's."""
    await _sync(org_id, policy_id, user_ids)


async def _sync(
    org_id: uuid.UUID,
    policy_id: uuid.UUID | None,
    user_ids: Collection[uuid.UUID] | None,
) -> bool:
    """:func:`sync_holidays`; False when there's no calendar to write to (no key saved)."""
    async with one_at_a_time(org_id):
        async with AsyncSessionLocal() as db:
            sync = await load_sync(db, org_id)
            if sync.key is None:
                return False
            plans = await _plans(db, org_id, sync, policy_id, user_ids)
        for plan in plans:
            await _write(org_id, sync, plan)
    return True


async def _write(org_id: uuid.UUID, sync: CalendarSync, plan: _Plan) -> None:
    try:
        await apply_events(sync, plan.email, HOLIDAY_TAG, plan.events, since=plan.since)
    except SYNC_ERRORS as exc:
        logger.warning(
            "leave_calendar_holidays_failed",
            org_id=str(org_id),
            user_id=str(plan.user_id),
            error=str(exc),
        )


async def _plans(
    db: AsyncSession,
    org_id: uuid.UUID,
    sync: CalendarSync,
    policy_id: uuid.UUID | None,
    user_ids: Collection[uuid.UUID] | None,
) -> list[_Plan]:
    default = await ensure_default_policy(db, org_id)
    people = await LeaveCalendarPeopleRepository(db, org_id=org_id).list_people(
        default, policy_id=policy_id, user_ids=user_ids
    )
    policies = await LeavePolicyRepository(db, org_id=org_id).by_ids({p.policy_id for p in people})
    by_policy: dict[uuid.UUID, tuple[dict[str, Event], datetime]] = {}
    for policy in policies.values():
        today = today_for(policy)
        holidays = {
            day: name
            for day, name in (await mandatory_holidays(db, policy, today, date.max)).items()
            if day.weekday() in policy.working_days  # a day off is no one's Out of office
        }
        events = holiday_events(holidays, policy.timezone, sync.options)
        since = datetime.combine(today, time(0), resolve_zone(policy.timezone))
        by_policy[policy.id] = (events if sync.options.enabled else {}, since)
    plans = []
    for person in people:
        if person.policy_id in by_policy:
            events, since = by_policy[person.policy_id]
            plans.append(_Plan(person.user_id, person.email, {} if person.left else events, since))
    return plans


async def after_holiday_change(org_id: uuid.UUID, policy_id: uuid.UUID, start: date) -> None:
    """A policy's holidays changed from ``start``: re-sync its holidays and WFH.

    WFH puts no Home on a holiday, so its days need re-checking too.
    """
    if not await _sync(org_id, policy_id, None):
        return
    async with AsyncSessionLocal() as db:
        wfh = await LeaveRequestRepository(db, org_id=org_id).active_between(
            None, start, date.max, kinds=[LeaveKind.WFH]
        )
        ids = [r.id for r in wfh if r.policy_id == policy_id and r.status == LeaveStatus.APPROVED]
    for request_id in ids:
        await sync_request(org_id, request_id)
