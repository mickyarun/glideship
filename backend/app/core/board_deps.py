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

"""FastAPI dependencies that resolve the caller's access to a board or card.

Routes declare the :class:`BoardAction` they perform; the minimum role
comes from ``BOARD_ACTION_MIN_ROLE``, so the role matrix lives in one
table. The rule itself lives in
:func:`app.services.boards.access.resolve_board_access`, and its errors
(404 for missing, foreign or invisible boards, 403 below the role, 409 for
a write to an archived board) are mapped by ``api/v1/_board_errors.py``.
"""

import re
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Depends, Header, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_deps import get_current_user, get_db
from app.core.permission_deps import PermissionSet, get_permission_set
from app.models.board_card import INT4_MAX
from app.models.user import User
from app.repositories.board import BoardRepository
from app.services.boards.access import (
    BoardAccess,
    BoardCaller,
    CardAccess,
    resolve_board_access,
    resolve_card,
)
from app.services.boards.constants import BOARD_ACTION_MIN_ROLE, BoardAction

# What a browser tab may send as its client id: a UUID, or anything shaped
# like one. Anything else is dropped rather than refused, since the id only
# lets a tab skip its own live events.
_CLIENT_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")


async def request_origin(
    x_client_id: str | None = Header(default=None, alias="X-Client-Id"),
) -> str | None:
    """The sending tab's id from ``X-Client-Id``, or None when absent or malformed."""
    if x_client_id is None or not _CLIENT_ID.match(x_client_id):
        return None
    return x_client_id


async def board_caller(
    current_user: User = Depends(get_current_user),
    perms: PermissionSet = Depends(get_permission_set),
) -> BoardCaller:
    """The caller of a boards route, with their org permissions."""
    return BoardCaller(user_id=current_user.id, org_id=current_user.org_id, perms=perms)


async def caller_has_boards(
    caller: BoardCaller = Depends(board_caller), db: AsyncSession = Depends(get_db)
) -> bool:
    """Whether the caller can open at least one board, for ``/auth/me``.

    Shares the request's cached permission set with the route.
    """
    repo = BoardRepository(db, org_id=caller.org_id)
    return await repo.any_visible(caller.user_id, caller.perms)


def _tag(resolver: Callable[..., Any], action: BoardAction, writable: bool) -> None:
    # Introspection hooks for the route-walk tests.
    resolver.board_action = action  # type: ignore[attr-defined]
    resolver.board_min_role = BOARD_ACTION_MIN_ROLE[action]  # type: ignore[attr-defined]
    resolver.board_writable = writable  # type: ignore[attr-defined]


def require_action(
    action: BoardAction, *, writable: bool | None = None
) -> Callable[..., Awaitable[BoardAccess]]:
    """Resolve the ``{key}`` board for a route that performs ``action``.

    ``writable`` (refuse an archived board) defaults to every action but
    viewing; pass it to override, as restoring a board does.

    Usage::

        @router.patch("/{key}")
        async def update_board(
            access: BoardAccess = Depends(require_action(BoardAction.EDIT_SETTINGS)),
        ): ...
    """
    write = action is not BoardAction.VIEW if writable is None else writable
    min_role = BOARD_ACTION_MIN_ROLE[action]

    async def _resolve(
        key: str = Path(...),
        current_user: User = Depends(get_current_user),
        perms: PermissionSet = Depends(get_permission_set),
        db: AsyncSession = Depends(get_db),
        origin: str | None = Depends(request_origin),
    ) -> BoardAccess:
        return await resolve_board_access(
            db,
            user_id=current_user.id,
            org_id=current_user.org_id,
            perms=perms,
            key=key,
            min_role=min_role,
            writable=write,
            origin=origin,
        )

    _tag(_resolve, action, write)
    return _resolve


def require_card_action(
    action: BoardAction, *, writable: bool | None = None
) -> Callable[..., Awaitable[CardAccess]]:
    """Like :func:`require_action`, then the ``{number}`` card on that board (404 if absent)."""
    board_dep = require_action(action, writable=writable)

    async def _resolve(
        number: int = Path(..., ge=1, le=INT4_MAX),
        access: BoardAccess = Depends(board_dep),
        db: AsyncSession = Depends(get_db),
    ) -> CardAccess:
        return await resolve_card(access, db, number)

    _tag(_resolve, action, board_dep.board_writable)  # type: ignore[attr-defined]
    return _resolve
