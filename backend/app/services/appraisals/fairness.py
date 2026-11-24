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

"""HR marking flagged results fair, so sharing everything ready includes them.

Only while the cycle is in review and only results not yet shared. Who
and when are kept on the appraisal; a review sent back to its manager is
scored again, so the mark goes with it (see :func:`.sharing.send_back`).
"""

import uuid
from collections.abc import Collection
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import AppraisalStatus, CycleStatus
from app.repositories.appraisal import AppraisalRepository
from app.services.appraisals.calibration import calibration
from app.services.appraisals.context import Caller
from app.services.appraisals.errors import AppraisalConflictError

NOT_SHARED = frozenset({AppraisalStatus.MANAGER_REVIEW, AppraisalStatus.CALIBRATION})


async def held_ids(db: AsyncSession, caller: Caller, cycle: AppraisalCycle) -> set[uuid.UUID]:
    """Flagged results HR hasn't found fair yet."""
    return {p.appraisal_id for p in (await calibration(db, caller, cycle)).people if p.held}


async def mark_fair(
    db: AsyncSession, caller: Caller, cycle: AppraisalCycle, ids: Collection[uuid.UUID]
) -> int:
    """Mark these results fair; how many were marked."""
    if cycle.status is not CycleStatus.REVIEWING:
        raise AppraisalConflictError("Results can be marked fair only while reviews are open.")
    visible = {p.appraisal_id for p in (await calibration(db, caller, cycle)).people}
    repo = AppraisalRepository(db, org_id=cycle.org_id)
    now, marked = datetime.now(UTC), 0
    for appraisal_id in set(ids) & visible:
        row = await repo.lock_row(appraisal_id)
        if row is None or row.status not in NOT_SHARED:
            continue
        row.looks_fair_at, row.looks_fair_by = now, caller.user_id
        marked += 1
    await db.flush()
    return marked
