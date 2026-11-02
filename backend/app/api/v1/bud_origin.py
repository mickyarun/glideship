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

"""A BUD's way back to the board: send it back, and its Origin panel.

Mounted under ``/api/v1/buds`` behind ``workspace:engineering``. Board
errors raised here map to HTTP through ``api/v1/_board_errors.py``.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.board_deps import board_caller
from app.core.deps import get_current_user, get_db, require_permissions
from app.models.user import User
from app.schemas.boards.handover import HandoverRead
from app.schemas.boards.handover_return import BUDOrigin, HandoverReturn
from app.services.boards.access import BoardCaller
from app.services.boards.cursor import CURSOR_MAX_LENGTH
from app.services.boards.handover_return import return_to_board
from app.services.boards.origin import bud_origin

router = APIRouter(tags=["buds"])


@router.post(
    "/{bud_id}/return-to-board",
    response_model=HandoverRead,
    dependencies=[Depends(require_permissions("buds:edit"))],
)
async def send_back(
    bud_id: uuid.UUID,
    body: HandoverReturn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HandoverRead:
    """Send the BUD back to its card; only before development starts."""
    return await return_to_board(
        db,
        org_id=current_user.org_id,
        bud_id=bud_id,
        actor_id=current_user.id,
        actor_name=current_user.name,
        reason=body.reason,
    )


@router.get(
    "/{bud_id}/origin",
    response_model=BUDOrigin,
    dependencies=[Depends(require_permissions("buds:view"))],
)
async def get_origin(
    bud_id: uuid.UUID,
    cursor: str | None = Query(default=None, max_length=CURSOR_MAX_LENGTH),
    limit: int | None = Query(default=None, ge=1, le=settings.boards.comments_page_size),
    caller: BoardCaller = Depends(board_caller),
    db: AsyncSession = Depends(get_db),
) -> BUDOrigin:
    """The card the BUD came from, newest comments first, if the caller can open its board."""
    return await bud_origin(db, caller, bud_id, cursor=cursor, limit=limit)
