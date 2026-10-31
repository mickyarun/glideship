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

"""Handing a card over to dev: preview, confirm, and the card's handovers.

Preview and confirm need an editor on the board who also holds
``workspace:engineering`` and ``buds:create`` (``buds:edit`` too, to link),
re-checked in the service for every request.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.boards._access import hand_over_card, view_card
from app.core.deps import get_db
from app.schemas.boards.handover import (
    HandoverConfirm,
    HandoverList,
    HandoverPreview,
    HandoverRequest,
    HandoverResult,
)
from app.services.boards import handover_confirm, handover_preview, handover_reads
from app.services.boards.access import CardAccess

router = APIRouter(tags=["boards"])

HANDOVERS = "/{key}/cards/{number}/handovers"


@router.get(HANDOVERS, response_model=HandoverList)
async def list_handovers(
    target: CardAccess = Depends(view_card), db: AsyncSession = Depends(get_db)
) -> HandoverList:
    """The card's handovers, oldest first, and whether the caller may hand it over now."""
    return await handover_reads.list_handovers(db, target)


@router.post(f"{HANDOVERS}/preview", response_model=HandoverPreview)
async def preview_handover(
    body: HandoverRequest,
    target: CardAccess = Depends(hand_over_card),
    db: AsyncSession = Depends(get_db),
) -> HandoverPreview:
    """The BUD a confirm would create or link, with similar open BUDs. Writes nothing."""
    return await handover_preview.preview(db, target, body)


@router.post(HANDOVERS, response_model=HandoverResult, status_code=status.HTTP_201_CREATED)
async def confirm_handover(
    body: HandoverConfirm,
    target: CardAccess = Depends(hand_over_card),
    db: AsyncSession = Depends(get_db),
) -> HandoverResult:
    """Hand the card over; a repeated ``idempotency_key`` returns the first result."""
    return await handover_confirm.confirm(db, target, body)
