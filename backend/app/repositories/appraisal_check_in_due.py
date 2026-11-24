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

"""Check-ins still to send, for the due-date reminders."""

import uuid
from collections.abc import Collection
from dataclasses import dataclass
from datetime import date

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal import Appraisal
from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_enums import AppraisalStatus
from app.models.employee_profile import EmployeeProfile


@dataclass(frozen=True)
class UnsentCheckIn:
    """One open check-in not sent yet: whose, which month, by when."""

    user_id: uuid.UUID
    period_start: date
    due_on: date


class AppraisalCheckInDueRepository:
    """Unsent check-ins, scoped to one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        """Initialize the repository."""
        self._db = db
        self._org = org_id

    async def unsent(self, cycle_ids: Collection[uuid.UUID]) -> list[UnsentCheckIn]:
        """Open, unsent check-ins with a due date in these cycles, unless withdrawn.

        Only ones whose opening was announced: the "ready" message goes first,
        never on the same day as a due reminder.
        """
        if not cycle_ids:
            return []
        check_in = AppraisalCheckIn
        result = await self._db.execute(
            select(EmployeeProfile.user_id, check_in.period_start, check_in.due_on)
            .join(EmployeeProfile, EmployeeProfile.id == check_in.profile_id)
            .join(
                Appraisal,
                and_(
                    Appraisal.cycle_id == check_in.cycle_id,
                    Appraisal.profile_id == check_in.profile_id,
                ),
            )
            .where(
                check_in.org_id == self._org,
                check_in.cycle_id.in_(list(cycle_ids)),
                check_in.closed_at.is_(None),
                check_in.sent_at.is_(None),
                check_in.due_on.is_not(None),
                check_in.notified_at.is_not(None),
                Appraisal.status != AppraisalStatus.WITHDRAWN,
            )
        )
        return [UnsentCheckIn(r.user_id, r.period_start, r.due_on) for r in result.all()]
