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

"""Handing a person's unfinished manager notes to their new primary manager."""

import uuid

from sqlalchemy import ColumnElement, case, literal_column, null, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.models.appraisal import Appraisal
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import CycleStatus, FeedbackStatus
from app.models.appraisal_manager_feedback import AppraisalManagerFeedback
from app.repositories.appraisal import OPEN
from app.repositories.base import rowcount


def _unless_sent(column: InstrumentedAttribute[bytes | None]) -> ColumnElement[bytes | None]:
    """The column's value on a sent note; nothing on an unsent draft."""
    return case((AppraisalManagerFeedback.sent_at.is_(None), null()), else_=column)


class AppraisalFeedbackMoveRepository:
    """Note moves, scoped to one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        """Initialize the repository."""
        self._db = db
        self._org = org_id

    async def move_open(self, profile_id: uuid.UUID, manager_user_id: uuid.UUID) -> int:
        """Hand the person's unfinished items to a new manager, where they now score.

        Unfinished: not sent, or sent but never finished (from before sending
        existed). An unsent draft was
        the old manager's alone, so it is cleared; a sent note keeps what the
        person could already read, for the new manager to finish. Only
        items whose appraisal moved with them: still in progress, in a
        cycle that hasn't closed, and scored by ``manager_user_id``. An item
        on a shared appraisal stays put, since the writer must be its scorer.
        """
        item = AppraisalManagerFeedback
        scored_by_new = (
            select(Appraisal.cycle_id)
            .join(AppraisalCycle, AppraisalCycle.id == Appraisal.cycle_id)
            .where(
                Appraisal.org_id == self._org,
                Appraisal.profile_id == profile_id,
                Appraisal.manager_user_id == manager_user_id,
                Appraisal.status.in_(OPEN),
                AppraisalCycle.status != CycleStatus.CLOSED,
            )
        )
        result = await self._db.execute(
            update(item)
            .where(
                item.org_id == self._org,
                item.profile_id == profile_id,
                or_(item.sent_at.is_(None), item.status == FeedbackStatus.OPEN),
                item.manager_user_id != manager_user_id,
                item.cycle_id.in_(scored_by_new),
            )
            .values(
                manager_user_id=manager_user_id,
                keep_note=_unless_sent(item.keep_note),
                try_note=_unless_sent(item.try_note),
                goal_notes=_unless_sent(item.goal_notes),
                goal_status=case(
                    (item.sent_at.is_(None), literal_column("'{}'::jsonb")),
                    else_=item.goal_status,
                ),
            )
        )
        return rowcount(result)
