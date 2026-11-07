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

"""Opening manager feedback items, as part of the hourly check-in tick.

On the first working day after a feedback period ends, each enrolled
person gets an item for their primary manager, due ``feedback_due_days``
after the period ends. As with check-ins, only the latest ended period opens, so someone
enrolled late isn't handed items that are already overdue. Items never
close on their own: one the manager never writes stays "not done" and
never blocks the review.
"""

import uuid
from datetime import date, timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal import Appraisal
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import AppraisalStatus, CycleStatus, FeedbackStatus
from app.models.appraisal_manager_feedback import AppraisalManagerFeedback
from app.models.employee_profile import EmployeeProfile
from app.repositories.appraisal_feedback import AppraisalFeedbackRepository
from app.services.appraisals.cadence import FEEDBACK_ITEMS, feedback_periods

logger = structlog.get_logger(__name__)


def latest_feedback_period(cycle: AppraisalCycle, today: date) -> tuple[date, date] | None:
    """The newest feedback period that has ended by ``today``, or None (pure)."""
    periods = feedback_periods(cycle.period_start, cycle.period_end, cycle.feedback_cadence)
    ended = [p for p in periods if p[1] < today]
    return ended[-1] if ended else None


def should_open_feedback(
    cycle: AppraisalCycle,
    appraisal: Appraisal,
    profile: EmployeeProfile,
    period: tuple[date, date],
    working: bool,
) -> bool:
    """Whether the person's item for ``period`` opens on this tick (pure)."""
    start, end = period
    joined, exited = profile.date_of_joining, profile.date_of_exit
    return (
        cycle.status is not CycleStatus.CLOSED
        and appraisal.status is not AppraisalStatus.WITHDRAWN
        and working
        and (joined is None or joined <= end)
        and (exited is None or exited >= start)
    )


async def feedback_pass(
    db: AsyncSession,
    cycle: AppraisalCycle,
    appraisals: list[Appraisal],
    profiles: dict[uuid.UUID, EmployeeProfile],
    today: date,
    working: bool,
) -> None:
    """Open the latest ended period's item for everyone who hasn't got one."""
    period = latest_feedback_period(cycle, today)
    cadence = FEEDBACK_ITEMS.get(cycle.feedback_cadence)
    if period is None or cadence is None:
        return
    repo = AppraisalFeedbackRepository(db, org_id=cycle.org_id)
    have = {(f.profile_id, f.period_start) for f in await repo.for_cycles([cycle.id])}
    for appraisal in appraisals:
        profile = profiles.get(appraisal.profile_id)
        if profile is None or (profile.id, period[0]) in have:
            continue
        if not should_open_feedback(cycle, appraisal, profile, period, working):
            continue
        try:
            async with db.begin_nested():
                await repo.create(
                    AppraisalManagerFeedback(
                        id=uuid.uuid4(),
                        org_id=cycle.org_id,
                        cycle_id=cycle.id,
                        profile_id=profile.id,
                        manager_user_id=appraisal.manager_user_id,
                        period_start=period[0],
                        period_end=period[1],
                        cadence=cadence,
                        due_on=period[1] + timedelta(days=cycle.feedback_due_days),
                        goal_status={},
                        status=FeedbackStatus.OPEN,
                    )
                )
        except Exception:
            logger.exception(
                "appraisal_feedback_open_failed",
                org_id=str(cycle.org_id),
                profile_id=str(profile.id),
            )
