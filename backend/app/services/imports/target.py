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

"""The board an import writes to, and who may import at all.

Importing into an existing board needs the board's ``import`` action
(admin); importing into a new board needs ``boards:create``. Both are
checked when the mapping is saved and again when the job runs, so a
role lost in between stops the import.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions_boards import BOARDS_CREATE
from app.models.external_import import ExternalImportSession
from app.repositories.board import BoardRepository
from app.repositories.board_access import BoardAccessRepository
from app.schemas.boards.import_mapping import ImportMapping, NewBoardTarget
from app.services.boards.access import (
    BoardAccess,
    BoardCaller,
    BoardNotFoundError,
    resolve_board_access,
)
from app.services.boards.board_service import insert_board
from app.services.boards.constants import BOARD_ACTION_MIN_ROLE, BoardAction
from app.services.boards.errors import BoardActionForbiddenError
from app.services.imports.errors import ImportStateError

NO_IMPORT_RIGHTS = "Importing needs permission to create boards, or admin on a board."
NO_CREATE_RIGHTS = "Importing into a new board needs permission to create boards."
NOT_MAPPED = "Review the import and save its mapping first."


async def check_may_import(db: AsyncSession, caller: BoardCaller) -> None:
    """Refuse callers who could import nowhere: no ``boards:create`` and admin on no board."""
    if caller.perms.has(BOARDS_CREATE):
        return
    repo = BoardAccessRepository(db, org_id=caller.org_id)
    if not await repo.administers_any(caller.user_id, caller.perms):
        raise BoardActionForbiddenError(NO_IMPORT_RIGHTS)


def check_may_create(caller: BoardCaller) -> None:
    """Refuse a new-board import without ``boards:create``."""
    if not caller.perms.has(BOARDS_CREATE):
        raise BoardActionForbiddenError(NO_CREATE_RIGHTS)


async def importer_access(db: AsyncSession, caller: BoardCaller, key: str) -> BoardAccess:
    """The caller's access to an existing board they may import into (404, 403 or 409 if not)."""
    return await resolve_board_access(
        db,
        user_id=caller.user_id,
        org_id=caller.org_id,
        perms=caller.perms,
        key=key,
        min_role=BOARD_ACTION_MIN_ROLE[BoardAction.IMPORT],
        writable=True,
    )


def session_mapping(session: ExternalImportSession) -> ImportMapping:
    """The saved mapping; refused when there is none yet."""
    if session.config is None:
        raise ImportStateError(NOT_MAPPED)
    return ImportMapping.model_validate(session.config)


async def target_access(
    db: AsyncSession, session: ExternalImportSession, caller: BoardCaller
) -> BoardAccess:
    """The board the session writes to, creating it (committed) the first time if it's new."""
    if session.board_id is None:
        target = session_mapping(session).target
        if not isinstance(target, NewBoardTarget):
            raise ImportStateError(NOT_MAPPED)
        check_may_create(caller)
        created = await insert_board(
            db,
            caller,
            key=target.key,
            name=target.name,
            description=target.description,
            visibility=target.visibility,
        )
        session.board_id = created.id
        await db.commit()
    board = await BoardRepository(db, org_id=caller.org_id).get_by_id(session.board_id)
    if board is None:
        raise BoardNotFoundError()
    return await importer_access(db, caller, board.key)
