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

"""Cards on a board: list a stage, create, read, edit, move (here or to another board),
archive, restore."""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.boards import _access as can
from app.config import settings
from app.core.deps import get_db
from app.models.bud import BUDPriority
from app.repositories.board_card_filters import CardQuery
from app.schemas.boards.card import (
    CardCreate,
    CardDetail,
    CardMove,
    CardMoveBoard,
    CardPage,
    CardUpdate,
)
from app.schemas.boards.text import SEARCH_MAX_LENGTH
from app.services.boards import card_board_move, card_edit, card_move, card_service
from app.services.boards.access import BoardAccess, CardAccess
from app.services.boards.cursor import CURSOR_MAX_LENGTH, decode_position_cursor
from app.services.boards.handover_chips import opens_buds
from app.services.boards.reads import card_detail

router = APIRouter(tags=["boards"])


@router.get("/{key}/cards", response_model=CardPage)
async def list_cards(
    stage_id: uuid.UUID | None = None,
    cursor: str | None = Query(default=None, max_length=CURSOR_MAX_LENGTH),
    limit: int | None = Query(default=None, ge=1, le=settings.boards.stage_page_size),
    q: str | None = Query(default=None, max_length=SEARCH_MAX_LENGTH),
    assignee: uuid.UUID | None = None,
    label: uuid.UUID | None = None,
    priority: BUDPriority | None = None,
    repo: uuid.UUID | None = None,
    archived: bool = False,
    access: BoardAccess = Depends(can.view_board),
    db: AsyncSession = Depends(get_db),
) -> CardPage:
    """One page of a stage's cards, or of the whole board when searching or archived.

    Pass ``next_cursor`` back as ``cursor`` for the next page.
    """
    query = CardQuery(
        stage_id=stage_id,
        limit=limit or settings.boards.stage_page_size,
        after=decode_position_cursor(cursor) if cursor else None,
        q=q,
        assignee=assignee,
        label=label,
        priority=priority,
        repo=repo,
        archived=archived,
    )
    return await card_service.list_cards(db, access, query)


@router.post("/{key}/cards", response_model=CardDetail, status_code=status.HTTP_201_CREATED)
async def create_card(
    body: CardCreate,
    access: BoardAccess = Depends(can.create_card),
    db: AsyncSession = Depends(get_db),
) -> CardDetail:
    """A new card at the bottom of its stage."""
    return await card_service.create_card(db, access, body)


@router.get("/{key}/cards/{number}", response_model=CardDetail)
async def get_card(
    target: CardAccess = Depends(can.view_card), db: AsyncSession = Depends(get_db)
) -> CardDetail:
    """One card."""
    access = target.access
    return await card_detail(db, access.board, target.card, opens_buds=opens_buds(access.perms))


@router.patch("/{key}/cards/{number}", response_model=CardDetail)
async def update_card(
    body: CardUpdate,
    target: CardAccess = Depends(can.edit_card),
    db: AsyncSession = Depends(get_db),
) -> CardDetail:
    """Edit a card's fields, assignees or labels."""
    return await card_edit.update_card(db, target, body)


@router.post("/{key}/cards/{number}/move", response_model=CardDetail)
async def move_card(
    body: CardMove,
    target: CardAccess = Depends(can.move_card),
    db: AsyncSession = Depends(get_db),
) -> CardDetail:
    """Move a card to a stage of this board, between two neighbours."""
    return await card_move.move_card(db, target, body)


@router.post("/{key}/cards/{number}/move-board", response_model=CardDetail)
async def move_card_to_board(
    body: CardMoveBoard,
    target: CardAccess = Depends(can.move_card),
    db: AsyncSession = Depends(get_db),
) -> CardDetail:
    """Move a card to another board you edit; it gets that board's next key."""
    return await card_board_move.move_to_board(db, target, body)


@router.post("/{key}/cards/{number}/archive", response_model=CardDetail)
async def archive_card(
    target: CardAccess = Depends(can.archive_card), db: AsyncSession = Depends(get_db)
) -> CardDetail:
    """Archive a card."""
    return await card_move.set_card_archived(db, target, archived=True)


@router.post("/{key}/cards/{number}/restore", response_model=CardDetail)
async def restore_card(
    target: CardAccess = Depends(can.archive_card), db: AsyncSession = Depends(get_db)
) -> CardDetail:
    """Restore an archived card to the bottom of its stage."""
    return await card_move.set_card_archived(db, target, archived=False)
