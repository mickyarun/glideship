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

"""A card's checklist and its history."""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.boards._access import edit_card, read_card
from app.config import settings
from app.core.deps import get_db
from app.schemas.boards.card_detail import (
    ChecklistItemCreate,
    ChecklistItemRead,
    ChecklistItemUpdate,
    ChecklistOrder,
    EventPage,
)
from app.services.boards import checklist_service, events
from app.services.boards.access import CardAccess

router = APIRouter(tags=["boards"])

CHECKLIST = "/{key}/cards/{number}/checklist"


@router.get(CHECKLIST, response_model=list[ChecklistItemRead])
async def list_items(
    target: CardAccess = Depends(read_card), db: AsyncSession = Depends(get_db)
) -> list[ChecklistItemRead]:
    """The card's checklist, top to bottom."""
    return await checklist_service.list_items(db, target)


@router.post(CHECKLIST, response_model=ChecklistItemRead, status_code=status.HTTP_201_CREATED)
async def add_item(
    body: ChecklistItemCreate,
    target: CardAccess = Depends(edit_card),
    db: AsyncSession = Depends(get_db),
) -> ChecklistItemRead:
    """Add a line at the bottom."""
    return await checklist_service.add_item(db, target, body)


@router.put(f"{CHECKLIST}/order", response_model=list[ChecklistItemRead])
async def reorder_items(
    body: ChecklistOrder,
    target: CardAccess = Depends(edit_card),
    db: AsyncSession = Depends(get_db),
) -> list[ChecklistItemRead]:
    """Put every line in a new order."""
    return await checklist_service.reorder_items(db, target, body)


@router.patch(f"{CHECKLIST}/{{item_id}}", response_model=ChecklistItemRead)
async def update_item(
    item_id: uuid.UUID,
    body: ChecklistItemUpdate,
    target: CardAccess = Depends(edit_card),
    db: AsyncSession = Depends(get_db),
) -> ChecklistItemRead:
    """Edit or tick a line."""
    return await checklist_service.update_item(db, target, item_id, body)


@router.delete(f"{CHECKLIST}/{{item_id}}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: uuid.UUID,
    target: CardAccess = Depends(edit_card),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a line."""
    await checklist_service.delete_item(db, target, item_id)


@router.get("/{key}/cards/{number}/events", response_model=EventPage)
async def list_events(
    before: uuid.UUID | None = None,
    limit: int | None = Query(default=None, ge=1, le=settings.boards.events_page_size),
    target: CardAccess = Depends(read_card),
    db: AsyncSession = Depends(get_db),
) -> EventPage:
    """The card's history, newest first."""
    return await events.list_events(db, target, before=before, limit=limit)
