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

"""The board access dependency: every board handler gets a :class:`BoardAccess`.

Board service functions take a ``BoardAccess``, so a call path that skipped
the check doesn't type-check. A caller with no role on the board, or a role
below the route's minimum, gets 404 rather than 403 so members-only boards
don't leak their existence.
"""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_deps import get_current_user, get_db
from app.core.permission_deps import PermissionSet, get_permission_set
from app.models.board import Board
from app.models.board_enums import BoardMemberRole
from app.models.user import User
from app.repositories.board_access import BoardAccessRepository


@dataclass(frozen=True)
class BoardAccess:
    """A board the caller may act on, and the role they hold on it."""

    board: Board
    role: BoardMemberRole
    user_id: uuid.UUID
    org_id: uuid.UUID


def require_board(min_role: BoardMemberRole) -> Callable[..., Awaitable[BoardAccess]]:
    """FastAPI dependency factory resolving the ``{key}`` path parameter to a board.

    Usage::

        admin_board = require_board(BoardMemberRole.ADMIN)

        @router.patch("/{key}")
        async def update_board(access: BoardAccess = Depends(admin_board)): ...
    """

    async def _resolve(
        key: str = Path(...),
        current_user: User = Depends(get_current_user),
        perms: PermissionSet = Depends(get_permission_set),
        db: AsyncSession = Depends(get_db),
    ) -> BoardAccess:
        found = await BoardAccessRepository(db, org_id=current_user.org_id).board_with_role(
            key, current_user.id, perms
        )
        if found is None or not found[1].at_least(min_role):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found.")
        board, role = found
        return BoardAccess(
            board=board, role=role, user_id=current_user.id, org_id=current_user.org_id
        )

    return _resolve
