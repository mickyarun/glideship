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

"""Moving appraisal rows from one account to another in a member merge.

Rows are keyed by employee profile, which the merge moves as a whole, so
only the user-id columns (who scores, who wrote or changed what) need
repointing here.
"""

import uuid

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.models.appraisal import Appraisal
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_evidence_link import AppraisalEvidenceLink
from app.models.appraisal_goal import AppraisalGoal
from app.models.appraisal_goal_value import AppraisalGoalValue
from app.models.appraisal_manager_feedback import AppraisalManagerFeedback
from app.models.appraisal_role_template import AppraisalRoleTemplate
from app.repositories.base import rowcount

# Goal revisions keep the original ``changed_by``: the history is
# append-only and records who acted at the time, like the audit log.
USER_COLUMNS: tuple[InstrumentedAttribute[uuid.UUID | None], ...] = (
    AppraisalCycle.created_by,
    Appraisal.manager_user_id,
    AppraisalGoal.proposed_by,
    AppraisalGoal.accepted_by,
    AppraisalManagerFeedback.manager_user_id,
    AppraisalEvidenceLink.added_by,
    AppraisalGoalValue.reported_by,
    AppraisalRoleTemplate.trends_approved_by,
    AppraisalRoleTemplate.updated_by,
)


class AppraisalMergeRepository:
    """Repoints appraisal user ids within one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        """Initialize the repository."""
        self._db = db
        self._org = org_id

    async def repoint_user(self, source: uuid.UUID, target: uuid.UUID) -> int:
        """Move every reference to ``source`` onto ``target``; rows changed."""
        changed = 0
        for column in USER_COLUMNS:
            model = column.class_
            result = await self._db.execute(
                update(model)
                .where(model.org_id == self._org, column == source)
                .values({column.key: target})
            )
            changed += rowcount(result)
        return changed
