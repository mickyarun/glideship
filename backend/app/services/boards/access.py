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

"""Resolve a caller's access to one board, as a typed :class:`BoardAccess`.

Board service functions take a ``BoardAccess``, so a call path that skipped
the check doesn't type-check. HTTP and MCP handlers both build it here and
map the errors below to their own responses.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board import Board
from app.models.board_enums import BoardMemberRole, BoardStatus
from app.repositories.board_access import BoardAccessRepository, PermissionChecker


class BoardNotFoundError(Exception):
    """No such board in the org, or the caller holds no role on it."""


class BoardForbiddenError(Exception):
    """The caller can see the board but their role is below what's needed."""


class BoardArchivedError(Exception):
    """The board is archived, so nothing on it can change."""


@dataclass(frozen=True)
class BoardAccess:
    """A board the caller may act on, and the role they hold on it."""

    board: Board
    role: BoardMemberRole
    user_id: uuid.UUID
    org_id: uuid.UUID


async def resolve_board_access(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    org_id: uuid.UUID,
    perms: PermissionChecker,
    key: str,
    min_role: BoardMemberRole,
    writable: bool = False,
) -> BoardAccess:
    """The caller's access to the board keyed ``key`` (case-insensitive).

    Raises:
        BoardNotFoundError: The board is missing, in another org, or the caller
            has no role on it, so members-only boards don't leak.
        BoardForbiddenError: The caller's role is below ``min_role``.
        BoardArchivedError: ``writable`` is set and the board is archived.
    """
    found = await BoardAccessRepository(db, org_id=org_id).board_with_role(
        key.upper(), user_id, perms
    )
    if found is None:
        raise BoardNotFoundError(key)
    board, role = found
    if not role.at_least(min_role):
        raise BoardForbiddenError(key)
    if writable and board.status is BoardStatus.ARCHIVED:
        raise BoardArchivedError(key)
    return BoardAccess(board=board, role=role, user_id=user_id, org_id=org_id)
