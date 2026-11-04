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

"""The check-in tick: opens, refreshes and closes check-ins for every org.

Runs hourly for every org with a running cycle, Slack or not. On a
working day after a check-in period ends, each enrolled person gets the
check-in for it. Open check-ins have their fact list refreshed once a
day. A check-in closes when the next one opens, or, for the last one in a
cycle, on the self-review due date; one closed with nothing added is
marked missed, which is shown and never held against anyone.
"""

from datetime import UTC, date, datetime, timedelta, tzinfo

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import AppraisalStatus, CheckInStatus
from app.repositories.appraisal import AppraisalRepository
from app.repositories.appraisal_check_in import AppraisalCheckInRepository
from app.repositories.appraisal_cycle import (
    AppraisalCycleRepository,
    CycleOrg,
    orgs_with_running_cycles,
)
from app.repositories.appraisal_identity import AppraisalIdentityRepository
from app.repositories.appraisal_role_template import AppraisalRoleTemplateRepository
from app.services.appraisals.cadence import CADENCE_MONTHS, slices
from app.services.appraisals.check_in_builder import create_check_in, refresh_check_in
from app.services.appraisals.enrolment import enrol_late_joiners
from app.services.leave.digest_settings import org_zone
from app.services.scheduling.tick_loop import run_tick_loop

logger = structlog.get_logger(__name__)
TICK_SECONDS = 3600
REFRESH_EVERY = timedelta(hours=20)
WEEKDAYS = [0, 1, 2, 3, 4]


def closes_on(cycle: AppraisalCycle, period_end: date) -> date:
    """The day a check-in for the period ending ``period_end`` closes (pure)."""
    periods = slices(cycle.period_start, cycle.period_end, CADENCE_MONTHS[cycle.checkin_cadence])
    later = [end for _, end in periods if end > period_end]
    # It closes when the next one opens: the day after the next period ends.
    return later[0] + timedelta(days=1) if later else cycle.self_due


def is_empty(check_in: AppraisalCheckIn, links: int, values: int) -> bool:
    """Nothing added by the person: no lines, tags, links or goal values."""
    return check_in.employee_note is None and not check_in.fact_tags and not (links or values)


async def _close(db: AsyncSession, check_in: AppraisalCheckIn, now: datetime) -> None:
    repo = AppraisalCheckInRepository(db, org_id=check_in.org_id)
    links = len(await repo.links(check_in.id))
    values = len(await repo.goal_values(check_in.id))
    if is_empty(check_in, links, values):
        check_in.status = CheckInStatus.MISSED
    check_in.closed_at = now


async def cycle_pass(
    db: AsyncSession, cycle: AppraisalCycle, today: date, working: bool, zone: tzinfo
) -> None:
    """Open due check-ins, refresh and close the rest, for one cycle."""
    org_id, now = cycle.org_id, datetime.now(UTC)
    appraisals = [
        a
        for a in await AppraisalRepository(db, org_id=org_id).for_cycle(cycle.id)
        if a.status is not AppraisalStatus.WITHDRAWN
    ]
    profiles = await AppraisalRepository(db, org_id=org_id).profiles_by_id(
        [a.profile_id for a in appraisals]
    )
    templates = {
        t.id: t for t in await AppraisalRoleTemplateRepository(db, org_id=org_id).list_for_org()
    }
    loose = await AppraisalIdentityRepository(db, org_id=org_id).accounts_without_profile()
    repo = AppraisalCheckInRepository(db, org_id=org_id)
    existing = {(c.profile_id, c.period_start): c for c in await repo.for_cycle(cycle.id)}
    periods = slices(cycle.period_start, cycle.period_end, CADENCE_MONTHS[cycle.checkin_cadence])
    for appraisal in appraisals:
        profile = profiles.get(appraisal.profile_id)
        if profile is None:
            continue
        template = (
            templates.get(appraisal.role_template_id) if appraisal.role_template_id else None
        )
        for start, end in periods:
            joined = profile.date_of_joining
            if end >= today or (joined is not None and joined > end):
                continue
            check_in = existing.get((profile.id, start))
            if check_in is None:
                if not working:
                    continue
                check_in = await create_check_in(
                    db, appraisal, profile, template, (start, end), loose, zone
                )
            elif check_in.closed_at is None and now - check_in.facts_at >= REFRESH_EVERY:
                await refresh_check_in(db, check_in, profile, template, loose, zone)
            if check_in.closed_at is None and today >= closes_on(cycle, end):
                await _close(db, check_in, now)
    await db.flush()


async def org_pass(db: AsyncSession, org: CycleOrg, now: datetime) -> None:
    """Late joiners first, then every running cycle."""
    zone = org_zone(org.config, org.policy_timezone, org.org_id)
    today = now.astimezone(zone).date()
    working = today.weekday() in (org.working_days or WEEKDAYS)
    await enrol_late_joiners(db, org.org_id, today)
    for cycle in await AppraisalCycleRepository(db, org_id=org.org_id).running():
        await cycle_pass(db, cycle, today, working, zone)


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
