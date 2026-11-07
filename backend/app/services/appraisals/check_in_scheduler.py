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

"""The creation tick: opens, refreshes and closes check-ins for every org.

Runs hourly for every org with a running cycle, Slack or not. On the
first working day (not a weekend or a holiday on the default leave
policy) after a check-in period ends, each enrolled person gets the
check-in for it. Only the latest ended period opens: someone enrolled
late isn't handed months that already passed, marked missed. Open
check-ins have their fact list refreshed once a day. A check-in closes
when its successor opens, the last one in a cycle on the self-review due
date, and all of them when HR closes the cycle; one closed with nothing
added is marked missed, which is shown and never held against anyone.
Manager feedback items open on the same tick (:mod:`.feedback_open`).
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, tzinfo

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.appraisal import Appraisal
from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import AppraisalStatus, CheckInStatus, CycleStatus
from app.models.appraisal_role_template import AppraisalRoleTemplate
from app.models.employee_profile import EmployeeProfile
from app.models.policy_holiday import HolidayKind
from app.repositories.appraisal import AppraisalRepository
from app.repositories.appraisal_check_in import AppraisalCheckInRepository
from app.repositories.appraisal_cycle import (
    AppraisalCycleRepository,
    CycleOrg,
    orgs_with_running_cycles,
)
from app.repositories.appraisal_identity import AppraisalIdentityRepository, LooseAccount
from app.repositories.appraisal_role_template import AppraisalRoleTemplateRepository
from app.repositories.policy_holiday import PolicyHolidayRepository
from app.services.appraisals.cadence import CADENCE_MONTHS, slices
from app.services.appraisals.check_in_builder import create_check_in, refresh_check_in
from app.services.appraisals.enrolment import enrol_late_joiners
from app.services.appraisals.feedback_open import feedback_pass
from app.services.leave.digest_settings import org_zone
from app.services.scheduling.tick_loop import run_tick_loop

logger = structlog.get_logger(__name__)
TICK_SECONDS = 3600
REFRESH_EVERY = timedelta(hours=20)
WEEKDAYS = [0, 1, 2, 3, 4]


@dataclass(frozen=True)
class Tick:
    """One pass's clock and calendar for an org."""

    now: datetime
    today: date
    working: bool
    zone: tzinfo


def latest_ended(cycle: AppraisalCycle, today: date) -> tuple[date, date] | None:
    """The newest check-in period that has ended by ``today``, or None (pure)."""
    periods = slices(cycle.period_start, cycle.period_end, CADENCE_MONTHS[cycle.checkin_cadence])
    ended = [p for p in periods if p[1] < today]
    return ended[-1] if ended else None


def is_empty(check_in: AppraisalCheckIn, link_ids: set[str], values: int) -> bool:
    """Nothing added by the person: no lines, links, goal values or live tags.

    Tags on facts that have dropped out of the list don't count: nothing
    would show for them.
    """
    live = {f["id"] for f in check_in.fact_refs or []} | link_ids
    tagged = any(key in live for key in check_in.fact_tags or {})
    return check_in.employee_note is None and not tagged and not (link_ids or values)


def should_open(
    cycle: AppraisalCycle,
    appraisal: Appraisal,
    profile: EmployeeProfile,
    period: tuple[date, date],
    tick: Tick,
) -> bool:
    """Whether the person's check-in for ``period`` opens on this tick (pure)."""
    start, end = period
    joined, exited = profile.date_of_joining, profile.date_of_exit
    return (
        cycle.status is not CycleStatus.CLOSED
        and appraisal.status is not AppraisalStatus.WITHDRAWN
        and tick.working
        and (joined is None or joined <= end)
        and (exited is None or exited >= start)
        # The last one would close at once: the self-review has opened.
        and not (end == cycle.period_end and tick.today >= cycle.self_due)
    )


async def _close(db: AsyncSession, check_in: AppraisalCheckIn, now: datetime) -> None:
    repo = AppraisalCheckInRepository(db, org_id=check_in.org_id)
    link_ids = {str(link.id) for link in await repo.links(check_in.id)}
    values = len(await repo.goal_values(check_in.id))
    if is_empty(check_in, link_ids, values):
        check_in.status = CheckInStatus.MISSED
    check_in.closed_at = now


async def _person_pass(
    db: AsyncSession,
    cycle: AppraisalCycle,
    appraisal: Appraisal,
    profile: EmployeeProfile,
    template: AppraisalRoleTemplate | None,
    mine: dict[date, AppraisalCheckIn],
    loose: Sequence[LooseAccount],
    tick: Tick,
) -> None:
    """Open, refresh and close one person's check-ins in one cycle."""
    latest = latest_ended(cycle, tick.today)
    if latest and latest[0] not in mine and should_open(cycle, appraisal, profile, latest, tick):
        mine[latest[0]] = await create_check_in(
            db, appraisal, profile, template, latest, loose, tick.zone, tick.now
        )
    running = cycle.status is not CycleStatus.CLOSED
    for start, check_in in sorted(mine.items()):
        if check_in.closed_at is not None:
            continue
        superseded = latest is not None and start < latest[0] and latest[0] in mine
        last_done = check_in.period_end == cycle.period_end and tick.today >= cycle.self_due
        if not running or superseded or last_done:
            await _close(db, check_in, tick.now)
        elif tick.now - check_in.facts_at >= REFRESH_EVERY:
            await refresh_check_in(db, check_in, profile, template, loose, tick.zone, tick.now)


async def cycle_pass(db: AsyncSession, cycle: AppraisalCycle, tick: Tick) -> None:
    """Each enrolled person's check-ins in one cycle; one failing never stops the rest."""
    org_id = cycle.org_id
    repo = AppraisalRepository(db, org_id=org_id)
    appraisals = await repo.for_cycle(cycle.id)
    profiles = await repo.profiles_by_id([a.profile_id for a in appraisals])
    templates = {
        t.id: t for t in await AppraisalRoleTemplateRepository(db, org_id=org_id).list_for_org()
    }
    loose = await AppraisalIdentityRepository(db, org_id=org_id).accounts_without_profile()
    by_person: dict[uuid.UUID, dict[date, AppraisalCheckIn]] = {}
    for check_in in await AppraisalCheckInRepository(db, org_id=org_id).for_cycle(cycle.id):
        by_person.setdefault(check_in.profile_id, {})[check_in.period_start] = check_in
    for appraisal in appraisals:
        profile = profiles.get(appraisal.profile_id)
        if profile is None:
            continue
        template_id = appraisal.role_template_id
        template = templates.get(template_id) if template_id else None
        mine = by_person.setdefault(profile.id, {})
        try:
            async with db.begin_nested():
                await _person_pass(db, cycle, appraisal, profile, template, mine, loose, tick)
        except Exception:
            logger.exception(
                "appraisal_check_in_person_failed", org_id=str(org_id), profile_id=str(profile.id)
            )
    await feedback_pass(db, cycle, appraisals, profiles, tick.today, tick.working)


async def org_pass(db: AsyncSession, org: CycleOrg, now: datetime) -> None:
    """Late joiners first, then every cycle that needs the tick."""
    zone = org_zone(org.config, org.policy_timezone, org.org_id)
    today = now.astimezone(zone).date()
    holidays = (
        await PolicyHolidayRepository(db, org_id=org.org_id).list_between(
            org.policy_id, today, today, kind=HolidayKind.MANDATORY
        )
        if org.policy_id
        else []
    )
    working = today.weekday() in (org.working_days or WEEKDAYS) and not holidays
    tick = Tick(now=now, today=today, working=working, zone=zone)
    await enrol_late_joiners(db, org.org_id, today)
    for cycle in await AppraisalCycleRepository(db, org_id=org.org_id).needing_pass():
        await cycle_pass(db, cycle, tick)


async def tick_once(now_utc: datetime | None = None) -> None:
    """One pass over every org; one org failing never stops the others."""
    now = now_utc or datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        orgs = await orgs_with_running_cycles(db)
    for org in orgs:
        try:
            async with AsyncSessionLocal() as db:
                await org_pass(db, org, now)
                await db.commit()
        except Exception:
            logger.exception("appraisal_check_in_org_failed", org_id=str(org.org_id))


async def run_check_in_scheduler() -> None:
    """The long-running loop started from the app's lifespan."""
    await run_tick_loop("appraisal_check_in", TICK_SECONDS, tick_once)
