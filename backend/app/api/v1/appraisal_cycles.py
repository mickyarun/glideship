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

"""HR's appraisal cycles: create, edit, check readiness, open, follow and close.

Every route needs ``appraisals:manage``.
"""

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._appraisal_deps import get_caller
from app.core.deps import get_db
from app.core.permission_deps import require_permissions
from app.core.permissions_people import APPRAISALS_MANAGE
from app.models.appraisal_cycle import AppraisalCycle
from app.repositories.appraisal_cycle import AppraisalCycleRepository
from app.schemas.appraisal_cycle import (
    CycleCreate,
    CycleProgress,
    CycleRead,
    CycleUpdate,
    EnrolmentReport,
    Readiness,
)
from app.schemas.appraisal_review import Calibration
from app.services.appraisals import cycles, sharing
from app.services.appraisals.calibration import calibration
from app.services.appraisals.context import Caller
from app.services.appraisals.enrolment import activate
from app.services.appraisals.errors import AppraisalNotFoundError
from app.services.appraisals.progress import cycle_progress
from app.services.appraisals.readiness import readiness
from app.services.appraisals.review_start import start_review

router = APIRouter(
    tags=["appraisals"], dependencies=[Depends(require_permissions(APPRAISALS_MANAGE))]
)


async def _cycle(db: AsyncSession, caller: Caller, cycle_id: uuid.UUID) -> AppraisalCycle:
    cycle = await AppraisalCycleRepository(db, org_id=caller.org_id).get_by_id(cycle_id)
    if cycle is None:
        raise AppraisalNotFoundError("Cycle not found.")
    return cycle


@router.get("/cycles", response_model=list[CycleRead])
async def list_cycles(
    caller: Caller = Depends(get_caller), db: AsyncSession = Depends(get_db)
) -> list[CycleRead]:
    """Recent cycles, newest first."""
    rows = await AppraisalCycleRepository(db, org_id=caller.org_id).list_recent()
    return [cycles.cycle_read(c) for c in rows]


@router.post("/cycles", response_model=CycleRead, status_code=status.HTTP_201_CREATED)
async def post_cycle(
    body: CycleCreate,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> CycleRead:
    """A draft cycle for the next period, prefilled from the org's settings."""
    return cycles.cycle_read(await cycles.create_cycle(db, caller.org_id, caller.user_id, body))


@router.get("/cycles/{cycle_id}", response_model=CycleRead)
async def get_cycle(
    cycle_id: uuid.UUID,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> CycleRead:
    """One cycle."""
    return cycles.cycle_read(await _cycle(db, caller, cycle_id))


@router.patch("/cycles/{cycle_id}", response_model=CycleRead)
async def patch_cycle(
    cycle_id: uuid.UUID,
    body: CycleUpdate,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> CycleRead:
    """Change a draft cycle."""
    return cycles.cycle_read(await cycles.update_cycle(db, caller.org_id, cycle_id, body))


@router.delete("/cycles/{cycle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cycle(
    cycle_id: uuid.UUID,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete a draft cycle."""
    await cycles.delete_cycle(db, caller.org_id, cycle_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/cycles/{cycle_id}/readiness", response_model=Readiness)
async def get_readiness(
    cycle_id: uuid.UUID,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> Readiness:
    """AI or manual, people HR should look at, and possible duplicate accounts."""
    return await readiness(db, await _cycle(db, caller, cycle_id))


@router.post("/cycles/{cycle_id}/activate", response_model=EnrolmentReport)
async def activate_cycle(
    cycle_id: uuid.UUID,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> EnrolmentReport:
    """Open the cycle and enrol everyone in its scope."""
    return await activate(db, caller.org_id, cycle_id, caller.user_id)


@router.get("/cycles/{cycle_id}/progress", response_model=CycleProgress)
async def get_progress(
    cycle_id: uuid.UUID,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> CycleProgress:
    """Who's done and who's overdue."""
    return await cycle_progress(db, caller, await _cycle(db, caller, cycle_id))


@router.post("/cycles/{cycle_id}/close", response_model=CycleRead)
async def close_cycle(
    cycle_id: uuid.UUID,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> CycleRead:
    """Close a running cycle; everything in it becomes read-only."""
    return cycles.cycle_read(await cycles.close_cycle(db, caller.org_id, cycle_id))


@router.post("/cycles/{cycle_id}/start-review", status_code=status.HTTP_202_ACCEPTED)
async def post_start_review(
    cycle_id: uuid.UUID,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Open the self-reviews; AI period summaries follow in the background."""
    return {"opened": await start_review(db, caller.org_id, cycle_id)}


@router.get("/cycles/{cycle_id}/calibration", response_model=Calibration)
async def get_calibration(
    cycle_id: uuid.UUID,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> Calibration:
    """Each manager's bands, agreement and big gaps."""
    return await calibration(db, caller, await _cycle(db, caller, cycle_id))


@router.post("/cycles/{cycle_id}/share")
async def post_share_all(
    cycle_id: uuid.UUID,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Share every review waiting for HR that the caller may act on."""
    return {"shared": await sharing.share_all(db, caller, await _cycle(db, caller, cycle_id))}
