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

"""The board access dependency: maps board access errors to HTTP statuses.

The rule itself lives in :func:`app.services.boards.access.resolve_board_access`.
Missing, foreign or invisible boards answer 404 so members-only boards don't
leak; a visible board with too low a role answers 403; a write to an
archived board answers 409.
"""

from collections.abc import Awaitable, Callable

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_deps import get_current_user, get_db
from app.core.permission_deps import PermissionSet, get_permission_set
from app.models.board_enums import BoardMemberRole
from app.models.user import User
from app.services.boards.access import (
    BoardAccess,
    BoardArchivedError,
    BoardForbiddenError,
    BoardNotFoundError,
    resolve_board_access,
)


def require_board(
    min_role: BoardMemberRole, *, writable: bool = False
) -> Callable[..., Awaitable[BoardAccess]]:
    """FastAPI dependency factory resolving the ``{key}`` path parameter to a board.

    Usage::

        admin_board = require_board(BoardMemberRole.ADMIN, writable=True)

        @router.patch("/{key}")
        async def update_board(access: BoardAccess = Depends(admin_board)): ...
    """

    async def _resolve(
        key: str = Path(...),
        current_user: User = Depends(get_current_user),
        perms: PermissionSet = Depends(get_permission_set),
        db: AsyncSession = Depends(get_db),
    ) -> BoardAccess:
        try:
            return await resolve_board_access(
                db,
                user_id=current_user.id,
                org_id=current_user.org_id,
                perms=perms,
                key=key,
                min_role=min_role,
                writable=writable,
            )
        except BoardNotFoundError:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Board not found.") from None
        except BoardForbiddenError:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Your role on this board doesn't allow this."
            ) from None
        except BoardArchivedError:
            raise HTTPException(status.HTTP_409_CONFLICT, "This board is archived.") from None

    return _resolve
