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

"""Find a card by its display key, live or old, with the caller's role on it.

A key like ``SEO-14`` is board ``SEO``, number 14: first the card with
that number on that board, else the card ``board_card_key_aliases`` says
had it before moving away. Either way the role comes from the card's
*current* board, in the same statement, so an old key never opens a card
on a board the caller can't see.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.board import Board
from app.models.board_card import INT4_MAX, BoardCard, BoardCardKeyAlias
from app.models.board_enums import BoardMemberRole
from app.repositories.board_access import BoardAccessRepository, PermissionChecker


def split_card_key(key: str) -> tuple[str, int] | None:
    """``"seo-14"`` → ``("SEO", 14)``; None when it isn't shaped like a card key."""
    board_key, sep, number = key.strip().upper().rpartition("-")
    if (
        not sep
        or not board_key
        or not (number.isascii() and number.isdigit())
        or int(number) > INT4_MAX
    ):
        return None
    return board_key, int(number)


class BoardCardKeyRepository:
    """Card key lookups and old keys for one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        self._db = db
        self._org_id = org_id

    def add_alias(self, card: BoardCard, board_id: uuid.UUID, number: int) -> None:
        """Remember that ``card`` was number ``number`` on ``board_id``."""
        self._db.add(
            BoardCardKeyAlias(
                org_id=self._org_id, board_id=board_id, number=number, card_id=card.id
            )
        )

    async def resolve(
        self, key: str, user_id: uuid.UUID, perms: PermissionChecker
    ) -> tuple[BoardCard, Board, BoardMemberRole] | None:
        """The card ``key`` names, its current board and the caller's role there."""
        parts = split_card_key(key)
        if parts is None:
            return None
        board_key, number = parts
        named, live_card = aliased(Board), aliased(BoardCard)
        live = (
            select(live_card.id)
            .join(named, named.id == live_card.board_id)
            .where(
                named.org_id == self._org_id, named.key == board_key, live_card.number == number
            )
            .scalar_subquery()
        )
        old_board = aliased(Board)
        old = (
            select(BoardCardKeyAlias.card_id)
            .join(old_board, old_board.id == BoardCardKeyAlias.board_id)
            .where(
                BoardCardKeyAlias.org_id == self._org_id,
                old_board.org_id == self._org_id,
                old_board.key == board_key,
                BoardCardKeyAlias.number == number,
            )
            .scalar_subquery()
        )
        roles = BoardAccessRepository(self._db, org_id=self._org_id).role_subquery(user_id, perms)
        stmt = (
            select(BoardCard, Board, roles.c.role)
            .join(Board, Board.id == BoardCard.board_id)
            .join(roles, roles.c.board_id == Board.id)
            .where(BoardCard.org_id == self._org_id, BoardCard.id == func.coalesce(live, old))
        )
        row = (await self._db.execute(stmt)).one_or_none()
        return None if row is None else (row[0], row[1], row[2])
