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

"""HR's view of a running cycle: progress, the fairness check, and reminding the late."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._appraisal_deps import get_caller
from app.api.v1.appraisal_cycles import load_cycle
from app.core.deps import get_db
from app.core.permission_deps import require_permissions
from app.core.permissions_people import APPRAISALS_MANAGE
from app.schemas.appraisal_calibration import Calibration, LooksFairBody
from app.schemas.appraisal_progress import CycleProgress, RemindResult
from app.services.appraisals.calibration import calibration
from app.services.appraisals.context import Caller
from app.services.appraisals.fairness import mark_fair
from app.services.appraisals.hr_remind import remind_late
from app.services.appraisals.progress import cycle_progress

router = APIRouter(
    tags=["appraisals"], dependencies=[Depends(require_permissions(APPRAISALS_MANAGE))]
)


@router.get("/cycles/{cycle_id}/progress", response_model=CycleProgress)
async def get_progress(
    cycle_id: uuid.UUID,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> CycleProgress:
    """Who's done and who's overdue."""
    return await cycle_progress(db, caller, await load_cycle(db, caller, cycle_id))


@router.post("/cycles/{cycle_id}/remind", response_model=RemindResult)
async def post_remind(
    cycle_id: uuid.UUID,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> RemindResult:
    """Slack everyone late in the cycle now: check-ins and managers' notes. Once a day."""
    return await remind_late(db, caller, await load_cycle(db, caller, cycle_id))


@router.get("/cycles/{cycle_id}/calibration", response_model=Calibration)
async def get_calibration(
    cycle_id: uuid.UUID,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> Calibration:
    """Each manager's bands, agreement and big gaps."""
    return await calibration(db, caller, await load_cycle(db, caller, cycle_id))


@router.post("/cycles/{cycle_id}/looks-fair")
async def post_looks_fair(
    cycle_id: uuid.UUID,
    body: LooksFairBody,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Mark flagged results fair, so sharing everything ready includes them."""
    cycle = await load_cycle(db, caller, cycle_id)
    return {"marked": await mark_fair(db, caller, cycle, body.appraisal_ids)}
