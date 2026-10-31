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

"""Boards: list, create, open, edit, archive and restore."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.boards import _access as can
from app.core.board_deps import board_caller
from app.core.deps import get_db, require_permissions
from app.core.permissions_boards import BOARDS_CREATE
from app.schemas.boards.board import BoardCreate, BoardDetail, BoardList, BoardUpdate
from app.services.boards import board_service, board_settings
from app.services.boards.access import BoardAccess, BoardCaller

router = APIRouter(tags=["boards"])


@router.get("", response_model=BoardList)
async def list_boards(
    archived: bool = Query(False, description="List the archived boards I hold a role on."),
    caller: BoardCaller = Depends(board_caller),
    db: AsyncSession = Depends(get_db),
) -> BoardList:
    """Boards I can open, then the Delivery board when I'm in engineering.

    With ``archived=true``, the archived boards I hold a role on instead (they
    open read-only; restoring stays with board admins), and no Delivery entry.
    """
    return await board_service.list_boards(db, caller, archived=archived)


@router.post(
    "",
    response_model=BoardDetail,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions(BOARDS_CREATE))],
)
async def create_board(
    body: BoardCreate,
    caller: BoardCaller = Depends(board_caller),
    db: AsyncSession = Depends(get_db),
) -> BoardDetail:
    """A new board from a template; I become its admin."""
    return await board_service.create_board(db, caller, body)


@router.get("/{key}", response_model=BoardDetail)
async def open_board(
    access: BoardAccess = Depends(can.view_board), db: AsyncSession = Depends(get_db)
) -> BoardDetail:
    """The board, its stages and labels, my role and what I may do.

    Also records my visit (throttled) for the switcher's recent list.
    """
    return await board_service.open_board(db, access)


@router.patch("/{key}", response_model=BoardDetail)
async def update_board(
    body: BoardUpdate,
    access: BoardAccess = Depends(can.edit_settings),
    db: AsyncSession = Depends(get_db),
) -> BoardDetail:
    """Change the board's settings."""
    return await board_settings.update_board(db, access, body)


@router.post("/{key}/archive", response_model=BoardDetail)
async def archive_board(
    access: BoardAccess = Depends(can.archive_board), db: AsyncSession = Depends(get_db)
) -> BoardDetail:
    """Archive the board; nothing on it can change until it's restored."""
    return await board_settings.set_archived(db, access, archived=True)


@router.post("/{key}/restore", response_model=BoardDetail)
async def restore(
    access: BoardAccess = Depends(can.restore_board), db: AsyncSession = Depends(get_db)
) -> BoardDetail:
    """Bring an archived board back."""
    return await board_settings.set_archived(db, access, archived=False)
