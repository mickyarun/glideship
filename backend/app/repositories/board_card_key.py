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

A key like ``SEO-14`` is first read as a live key (board ``SEO``, number
14), then looked up in ``board_card_key_aliases``. Either way the role
comes from the card's *current* board, in the same statement, so an old
key never opens a card on a board the caller can't see.
"""

import uuid

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.board import Board
from app.models.board_card import INT4_MAX, BoardCard, BoardCardKeyAlias
from app.models.board_enums import BoardMemberRole
from app.repositories.board_access import BoardAccessRepository, PermissionChecker


def split_card_key(key: str) -> tuple[str, int] | None:
    """``"seo-14"`` → ``("SEO", 14)``; None when it isn't shaped like a card key."""
    board_key, sep, number = key.strip().upper().rpartition("-")
    if not sep or not board_key or not number.isdigit() or int(number) > INT4_MAX:
        return None
    return board_key, int(number)


class BoardCardKeyRepository:
    """Card key lookups for one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        self._db = db
        self._org_id = org_id

    async def resolve(
        self, key: str, user_id: uuid.UUID, perms: PermissionChecker
    ) -> tuple[BoardCard, Board, BoardMemberRole] | None:
        """The card ``key`` names, its current board and the caller's role there."""
        normalised = key.strip().upper()
        alias = (
            select(BoardCardKeyAlias.card_id)
            .where(BoardCardKeyAlias.org_id == self._org_id, BoardCardKeyAlias.key == normalised)
            .scalar_subquery()
        )
        card_id: ColumnElement[uuid.UUID] = alias
        parts = split_card_key(key)
        if parts is not None:
            live_card, live_board = aliased(BoardCard), aliased(Board)
            live = (
                select(live_card.id)
                .join(live_board, live_board.id == live_card.board_id)
                .where(
                    live_board.org_id == self._org_id,
                    live_board.key == parts[0],
                    live_card.number == parts[1],
                )
                .scalar_subquery()
            )
            card_id = func.coalesce(live, alias)
        roles = BoardAccessRepository(self._db, org_id=self._org_id).role_subquery(user_id, perms)
        stmt = (
            select(BoardCard, Board, roles.c.role)
            .join(Board, Board.id == BoardCard.board_id)
            .join(roles, roles.c.board_id == Board.id)
            .where(BoardCard.org_id == self._org_id, BoardCard.id == card_id)
        )
        row = (await self._db.execute(stmt)).one_or_none()
        return None if row is None else (row[0], row[1], row[2])
