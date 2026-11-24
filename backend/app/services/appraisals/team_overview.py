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

"""The manager's "Everyone" table: each report, month by month.

A check-in's state is what a manager may know: sent, or not sent yet
(late once past due), or missed once it closed unsent, never whether the
person has started writing. A month that hasn't opened shows as such.
"""

import uuid
from collections import defaultdict
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import FeedbackStatus
from app.models.appraisal_manager_feedback import AppraisalManagerFeedback
from app.repositories.appraisal_check_in import AppraisalCheckInRepository
from app.repositories.appraisal_cycle import AppraisalCycleRepository
from app.repositories.appraisal_feedback import AppraisalFeedbackRepository
from app.schemas.appraisal_team import MonthState, MonthStateName, NoteState, TeamRow
from app.services.appraisals.appraisal_lists import team_appraisals
from app.services.appraisals.cadence import CADENCE_MONTHS, slices
from app.services.appraisals.context import Caller
from app.services.appraisals.due_dates import is_late
from app.services.appraisals.org_clock import org_today


def month_state(check_in: AppraisalCheckIn | None, today: date) -> MonthStateName:
    """What a manager may know of one month's check-in (pure)."""
    if check_in is None:
        return "not_open"
    if check_in.sent_at is not None:
        return "sent"
    if check_in.closed_at is not None:
        return "missed"
    return "late" if is_late(check_in.due_on, None, today) else "open"


def _months(
    cycle: AppraisalCycle, mine: dict[date, AppraisalCheckIn], today: date
) -> list[MonthState]:
    out = []
    for start, end in slices(
        cycle.period_start, cycle.period_end, CADENCE_MONTHS[cycle.checkin_cadence]
    ):
        check_in = mine.get(start)
        out.append(
            MonthState(
                period_start=start,
                period_end=end,
                check_in_id=check_in.id if check_in else None,
                state=month_state(check_in, today),
                due_on=check_in.due_on if check_in else None,
            )
        )
    return out


def _by_period(item: AppraisalManagerFeedback) -> date:
    return item.period_start


async def team_overview(db: AsyncSession, caller: Caller) -> list[TeamRow]:
    """The caller's reports in running cycles, with each month and each note."""
    org_id = caller.org_id
    cycles = {c.id: c for c in await AppraisalCycleRepository(db, org_id=org_id).running()}
    rows = [r for r in await team_appraisals(db, caller) if r.cycle_id in cycles]
    today = await org_today(db, org_id)
    check_ins: dict[tuple[uuid.UUID, uuid.UUID], dict[date, AppraisalCheckIn]] = defaultdict(dict)
    repo = AppraisalCheckInRepository(db, org_id=org_id)
    for cycle_id in cycles:
        for check_in in await repo.for_cycle(cycle_id):
            check_ins[(cycle_id, check_in.profile_id)][check_in.period_start] = check_in
    notes: dict[tuple[uuid.UUID, uuid.UUID], list[AppraisalManagerFeedback]] = defaultdict(list)
    for item in await AppraisalFeedbackRepository(db, org_id=org_id).for_cycles(list(cycles)):
        notes[(item.cycle_id, item.profile_id)].append(item)
    return [
        TeamRow(
            **row.model_dump(),
            months=_months(cycles[row.cycle_id], check_ins[(row.cycle_id, row.profile_id)], today),
            notes=[
                NoteState(
                    id=i.id,
                    period_start=i.period_start,
                    period_end=i.period_end,
                    sent=i.status is FeedbackStatus.DONE,
                    due_on=i.due_on,
                    late=is_late(i.due_on, i.sent_at, today),
                )
                for i in sorted(
                    notes[(row.cycle_id, row.profile_id)], key=lambda n: n.period_start
                )
            ],
        )
        for row in rows
    ]
