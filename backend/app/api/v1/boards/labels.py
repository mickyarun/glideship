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

"""A board's labels: anyone on it can list them, admins change them."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.boards._access import manage_labels, view_board
from app.core.deps import get_db
from app.schemas.boards.label import LabelCreate, LabelRead, LabelUpdate
from app.services.boards import label_service
from app.services.boards.access import BoardAccess

router = APIRouter(tags=["boards"])


@router.get("/{key}/labels", response_model=list[LabelRead])
async def list_labels(
    access: BoardAccess = Depends(view_board), db: AsyncSession = Depends(get_db)
) -> list[LabelRead]:
    """The board's labels, by name."""
    return await label_service.list_labels(db, access)


@router.post("/{key}/labels", response_model=LabelRead, status_code=status.HTTP_201_CREATED)
async def create_label(
    body: LabelCreate,
    access: BoardAccess = Depends(manage_labels),
    db: AsyncSession = Depends(get_db),
) -> LabelRead:
    """Add a label."""
    return await label_service.create_label(db, access, body)


@router.patch("/{key}/labels/{label_id}", response_model=LabelRead)
async def update_label(
    label_id: uuid.UUID,
    body: LabelUpdate,
    access: BoardAccess = Depends(manage_labels),
    db: AsyncSession = Depends(get_db),
) -> LabelRead:
    """Rename or recolour a label."""
    return await label_service.update_label(db, access, label_id, body)


@router.delete("/{key}/labels/{label_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_label(
    label_id: uuid.UUID,
    access: BoardAccess = Depends(manage_labels),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a label; cards carrying it lose it."""
    await label_service.delete_label(db, access, label_id)
