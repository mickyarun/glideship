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

from app.core.permissions import WORKSPACE_ENGINEERING
from app.models.board import Board
from app.models.board_card import BoardCard
from app.models.board_enums import BoardMemberRole, BoardStatus
from app.repositories.board_access import BoardAccessRepository, PermissionChecker
from app.repositories.board_card import BoardCardRepository
from app.repositories.board_card_key import BoardCardKeyRepository
from app.services.boards.constants import (
    ARCHIVED_BOARD_ACTIONS,
    BOARD_ACTION_MIN_ROLE,
    BoardAction,
)
from app.services.boards.errors import (
    BoardActionForbiddenError,
    BoardConflictError,
    BoardItemNotFoundError,
)


class BoardNotFoundError(BoardItemNotFoundError):
    """No such board in the org, or the caller holds no role on it."""

    def __init__(self) -> None:
        super().__init__("Board not found.")


class BoardForbiddenError(BoardActionForbiddenError):
    """The caller can see the board but their role is below what's needed."""

    def __init__(self) -> None:
        super().__init__("Your role on this board doesn't allow this.")


class BoardArchivedError(BoardConflictError):
    """The board is archived, so nothing on it can change."""

    def __init__(self) -> None:
        super().__init__("This board is archived.")


@dataclass(frozen=True)
class BoardAccess:
    """A board the caller may act on, their role on it and their org permissions.

    ``perms`` lets an action also require an org permission (handing a card
    over needs ``buds:create``), on top of the board role.
    """

    board: Board
    role: BoardMemberRole
    user_id: uuid.UUID
    org_id: uuid.UUID
    perms: PermissionChecker

    def may(self, action: BoardAction) -> bool:
        """Whether the caller may take ``action`` on the board as it is now."""
        if self.board.status is BoardStatus.ARCHIVED and action not in ARCHIVED_BOARD_ACTIONS:
            return False
        return self.role.at_least(BOARD_ACTION_MIN_ROLE[action])

    def capabilities(self) -> list[BoardAction]:
        """Every action the caller may take now, in declaration order."""
        return [action for action in BoardAction if self.may(action)]


@dataclass(frozen=True)
class BoardCaller:
    """Who is calling a boards route that doesn't name a board."""

    user_id: uuid.UUID
    org_id: uuid.UUID
    perms: PermissionChecker

    @property
    def has_engineering(self) -> bool:
        """Whether the caller can open the engineering workspace, and so the BUD board."""
        return self.perms.has(WORKSPACE_ENGINEERING)


@dataclass(frozen=True)
class CardAccess:
    """A card on a board the caller may act on."""

    access: BoardAccess
    card: BoardCard


CARD_NOT_FOUND = "Card not found."


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
        raise BoardNotFoundError()
    board, role = found
    if not role.at_least(min_role):
        raise BoardForbiddenError()
    if writable and board.status is BoardStatus.ARCHIVED:
        raise BoardArchivedError()
    return BoardAccess(board=board, role=role, user_id=user_id, org_id=org_id, perms=perms)


async def resolve_card(access: BoardAccess, db: AsyncSession, number: int) -> CardAccess:
    """The card numbered ``number`` on the caller's board.

    Raises:
        BoardItemNotFoundError: The board has no such card.
    """
    repo = BoardCardRepository(db, org_id=access.org_id)
    card = await repo.get_by_number(access.board.id, number)
    if card is None:
        raise BoardItemNotFoundError(CARD_NOT_FOUND)
    return CardAccess(access=access, card=card)


async def resolve_card_by_key(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    org_id: uuid.UUID,
    perms: PermissionChecker,
    key: str,
) -> CardAccess:
    """The card a live or old key names, with the caller's role on its current board.

    Raises:
        BoardItemNotFoundError: No such key, or the caller holds no role on
            the card's current board.
    """
    found = await BoardCardKeyRepository(db, org_id=org_id).resolve(key, user_id, perms)
    if found is None:
        raise BoardItemNotFoundError(CARD_NOT_FOUND)
    card, board, role = found
    access = BoardAccess(board=board, role=role, user_id=user_id, org_id=org_id, perms=perms)
    return CardAccess(access=access, card=card)
