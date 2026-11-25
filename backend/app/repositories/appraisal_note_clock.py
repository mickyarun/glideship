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

"""Notes still waiting for a due date whose check-in has since been answered."""

import uuid
from datetime import datetime

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_manager_feedback import AppraisalManagerFeedback


class AppraisalNoteClockRepository:
    """Undated notes, scoped to one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        """Initialize the repository."""
        self._db = db
        self._org = org_id

    async def ready_to_date(
        self, cycle_id: uuid.UUID
    ) -> list[tuple[AppraisalManagerFeedback, datetime, datetime]]:
        """Unsent notes with no due date whose check-in was sent or has closed.

        Each comes with when its check-in was answered (the send, or the
        close for one that closed unsent) and when the note opened. The
        check-in is the one whose period ends with the note's: a quarterly
        note waits for the quarter's last. A note with no such check-in (a
        late joiner into a quarter, a leaver mid-quarter, a missed tick)
        counts as answered when it opened: check-ins open before notes on
        the same tick, so none will come later.
        """
        item, check_in = AppraisalManagerFeedback, AppraisalCheckIn
        answered = case(
            (check_in.id.is_(None), item.created_at),
            else_=func.coalesce(check_in.sent_at, check_in.closed_at),
        )
        result = await self._db.execute(
            select(item, answered, item.created_at)
            .outerjoin(
                check_in,
                and_(
                    check_in.org_id == item.org_id,
                    check_in.cycle_id == item.cycle_id,
                    check_in.profile_id == item.profile_id,
                    check_in.period_end == item.period_end,
                ),
            )
            .where(
                item.org_id == self._org,
                item.cycle_id == cycle_id,
                item.due_on.is_(None),
                item.sent_at.is_(None),
                answered.is_not(None),
            )
        )
        return [(row[0], row[1], row[2]) for row in result.all()]
