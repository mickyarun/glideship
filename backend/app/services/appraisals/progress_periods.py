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

"""Per-period totals for HR's cycle page: check-ins and notes sent (pure)."""

from collections import defaultdict
from collections.abc import Sequence
from datetime import date

from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import FeedbackStatus
from app.models.appraisal_manager_feedback import AppraisalManagerFeedback
from app.schemas.appraisal_progress import PeriodCount
from app.services.appraisals.cadence import CADENCE_MONTHS, slices


def slices_of(cycle: AppraisalCycle) -> list[tuple[date, date]]:
    """The cycle's check-in periods, in order."""
    return slices(cycle.period_start, cycle.period_end, CADENCE_MONTHS[cycle.checkin_cadence])


def _earliest(days: Sequence[date | None]) -> date | None:
    known = [d for d in days if d is not None]
    return min(known) if known else None


def check_in_periods(
    periods: list[tuple[date, date]], people: list[dict[date, AppraisalCheckIn]]
) -> list[PeriodCount]:
    """Each period: how many of the people still in it sent theirs, out of everyone."""
    out = []
    for start, end in periods:
        opened = [p[start] for p in people if start in p]
        out.append(
            PeriodCount(
                period_start=start,
                period_end=end,
                due_on=_earliest([c.due_on for c in opened]),
                sent=sum(c.sent_at is not None for c in opened),
                total=len(people),
            )
        )
    return out


def note_periods(items: list[AppraisalManagerFeedback]) -> list[PeriodCount]:
    """Each note period that has opened: how many notes are finished, out of how many."""
    by_period: dict[tuple[date, date], list[AppraisalManagerFeedback]] = defaultdict(list)
    for item in items:
        by_period[(item.period_start, item.period_end)].append(item)
    return [
        PeriodCount(
            period_start=start,
            period_end=end,
            due_on=_earliest([i.due_on for i in group]),
            sent=sum(i.status is FeedbackStatus.DONE for i in group),
            total=len(group),
        )
        for (start, end), group in sorted(by_period.items())
    ]
