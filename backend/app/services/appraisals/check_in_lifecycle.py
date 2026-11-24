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

"""When a check-in opens and closes (the rules the creation tick follows).

Only the latest ended period opens, for someone enrolled and employed
in it, on a working day. One that closes with nothing added is marked
missed, which is shown and never held against anyone.
"""

from dataclasses import dataclass
from datetime import date, datetime, tzinfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal import Appraisal
from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import AppraisalStatus, CheckInStatus, CycleStatus
from app.models.employee_profile import EmployeeProfile
from app.repositories.appraisal_check_in import AppraisalCheckInRepository
from app.repositories.appraisal_goal_value import AppraisalGoalValueRepository
from app.services.appraisals.cadence import CADENCE_MONTHS, slices


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


async def close_check_in(db: AsyncSession, check_in: AppraisalCheckIn, now: datetime) -> None:
    """Close a check-in; one with nothing added is marked missed."""
    repo = AppraisalCheckInRepository(db, org_id=check_in.org_id)
    link_ids = {str(link.id) for link in await repo.links(check_in.id)}
    values = len(
        await AppraisalGoalValueRepository(db, org_id=check_in.org_id).for_check_in(check_in.id)
    )
    if is_empty(check_in, link_ids, values):
        check_in.status = CheckInStatus.MISSED
    check_in.closed_at = now
