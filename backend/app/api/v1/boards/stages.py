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

"""A board's stages (admin only)."""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.boards._access import manage_stages
from app.core.deps import get_db
from app.schemas.boards.stage import StageCreate, StageOrder, StageRead, StageUpdate
from app.services.boards import stage_service
from app.services.boards.access import BoardAccess

router = APIRouter(tags=["boards"])


@router.post("/{key}/stages", response_model=StageRead, status_code=status.HTTP_201_CREATED)
async def create_stage(
    body: StageCreate,
    access: BoardAccess = Depends(manage_stages),
    db: AsyncSession = Depends(get_db),
) -> StageRead:
    """Add a stage at the right-hand end."""
    return await stage_service.create_stage(db, access, body)


@router.put("/{key}/stages/order", response_model=list[StageRead])
async def reorder_stages(
    body: StageOrder,
    access: BoardAccess = Depends(manage_stages),
    db: AsyncSession = Depends(get_db),
) -> list[StageRead]:
    """Put every stage in a new left-to-right order."""
    return await stage_service.reorder_stages(db, access, body)


@router.patch("/{key}/stages/{stage_id}", response_model=StageRead)
async def update_stage(
    stage_id: uuid.UUID,
    body: StageUpdate,
    access: BoardAccess = Depends(manage_stages),
    db: AsyncSession = Depends(get_db),
) -> StageRead:
    """Rename, re-categorise, set the WIP limit or make it the default."""
    return await stage_service.update_stage(db, access, stage_id, body)


@router.delete("/{key}/stages/{stage_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stage(
    stage_id: uuid.UUID,
    move_to: uuid.UUID | None = Query(default=None),
    access: BoardAccess = Depends(manage_stages),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a stage, moving its cards to ``move_to`` first."""
    await stage_service.delete_stage(db, access, stage_id, move_to)
