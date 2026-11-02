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

"""Data access for board cards, scoped to an organization."""

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board import Board
from app.models.board_card import BoardCard
from app.repositories.base import BaseRepository, rowcount


class BoardCardRepository(BaseRepository[BoardCard]):
    """Tenant-scoped repository for board cards."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        super().__init__(BoardCard, db, org_id=org_id)

    async def allocate_card_numbers(self, board_id: uuid.UUID, n: int) -> range:
        """Claim the board's next ``n`` card numbers in one statement.

        The counter only goes up, so a number is never handed out twice,
        even after its card moves to another board. The UPDATE locks the
        board row until the transaction ends, so call this late in the
        transaction: concurrent claims on the board wait for the commit.
        ``updated_at`` is left alone; claiming numbers isn't a board edit.

        Raises:
            ValueError: ``n`` is below 1.
            LookupError: No such board in this org.
        """
        if n < 1:
            raise ValueError("allocate at least one card number")
        stmt = (
            update(Board)
            .where(Board.id == board_id, Board.org_id == self._org_id)
            .values(next_card_number=Board.next_card_number + n, updated_at=Board.updated_at)
            .returning(Board.next_card_number)
        )
        end = (await self._db.execute(stmt)).scalar_one_or_none()
        if end is None:
            raise LookupError(f"board {board_id} not found")
        return range(end - n, end)

    async def release_card_numbers(self, board_id: uuid.UUID, numbers: range) -> bool:
        """Give back the last numbers claimed, when nobody claimed after them.

        Only safe while this transaction still holds the board row from its
        own :meth:`allocate_card_numbers`; then the counter still ends at
        ``numbers.stop`` and it moves back to ``numbers.start``.
        """
        stmt = (
            update(Board)
            .where(
                Board.id == board_id,
                Board.org_id == self._org_id,
                Board.next_card_number == numbers.stop,
            )
            .values(next_card_number=numbers.start, updated_at=Board.updated_at)
        )
        return rowcount(await self._db.execute(stmt)) == 1

    async def get_by_number(self, board_id: uuid.UUID, number: int) -> BoardCard | None:
        """The board's card with this number."""
        stmt = self._scoped(
            select(BoardCard).where(BoardCard.board_id == board_id, BoardCard.number == number)
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def get_in_board(self, board_id: uuid.UUID, card_id: uuid.UUID) -> BoardCard | None:
        """One card, or None when it isn't on this board."""
        stmt = self._scoped(
            select(BoardCard).where(BoardCard.id == card_id, BoardCard.board_id == board_id)
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def lock(self, card: BoardCard) -> None:
        """Hold the card's row until the transaction ends, and re-read it.

        Writers that also lock a stage take the stage lock first, the same
        order a stage delete uses, so the two can't deadlock.
        """
        await self._db.refresh(card, with_for_update=True)
