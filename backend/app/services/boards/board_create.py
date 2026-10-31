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


"""Checking and inserting a new board: its key, its name, and its first admin.

Shared by POST /boards and imports into a new board, so both refuse
the same keys and names with the same messages.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board import Board
from app.models.board_enums import BoardMemberRole, BoardVisibility
from app.repositories.board import BoardRepository
from app.repositories.board_member import BoardMemberRepository
from app.services.boards.access import BoardCaller
from app.services.boards.constants import BOARD_KEY_PATTERN, RESERVED_BOARD_KEYS
from app.services.boards.errors import BOARD_TAKEN, BoardConflictError, BoardRuleError


def normalise_key(raw: str) -> str:
    """An upper-case board key, or :class:`BoardRuleError` when it can't be one."""
    key = raw.strip().upper()
    if not BOARD_KEY_PATTERN.fullmatch(key):
        raise BoardRuleError("A board key is 2 to 10 letters, A to Z.")
    if key in RESERVED_BOARD_KEYS:
        raise BoardRuleError(f"{key} is reserved; pick another key.")
    return key


async def check_new_board(db: AsyncSession, caller: BoardCaller, *, key: str, name: str) -> str:
    """The normalised key, once the key is valid and neither it nor ``name`` is taken."""
    normal = normalise_key(key)
    repo = BoardRepository(db, org_id=caller.org_id)
    if await repo.key_or_name_taken(key=normal, name=name):
        raise BoardConflictError(BOARD_TAKEN)
    return normal


async def insert_board(
    db: AsyncSession,
    caller: BoardCaller,
    *,
    key: str,
    name: str,
    description: str | None,
    visibility: BoardVisibility,
) -> Board:
    """A new board with no stages yet and the caller as its admin; not committed."""
    board = Board(
        org_id=caller.org_id,
        name=name,
        key=await check_new_board(db, caller, key=key, name=name),
        description=description,
        visibility=visibility,
        created_by=caller.user_id,
    )
    if not await BoardRepository(db, org_id=caller.org_id).insert(board):
        raise BoardConflictError(BOARD_TAKEN)
    await BoardMemberRepository(db, org_id=caller.org_id).put_member(
        board.id, caller.user_id, BoardMemberRole.ADMIN
    )
    return board
