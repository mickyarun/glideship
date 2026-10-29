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

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board import Board
from app.models.board_card import BoardCard
from app.repositories.base import BaseRepository


class BoardCardRepository(BaseRepository[BoardCard]):
    """Tenant-scoped repository for board cards."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        super().__init__(BoardCard, db, org_id=org_id)
        self._org = org_id

    async def allocate_card_numbers(self, board_id: uuid.UUID, n: int) -> range:
        """Claim the board's next ``n`` card numbers in one statement.

        The counter only goes up, so a number is never handed out twice,
        even after its card moves to another board. The row lock taken by
        the UPDATE serialises concurrent claims until the caller commits.

        Raises:
            ValueError: ``n`` is below 1.
            LookupError: No such board in this org.
        """
        if n < 1:
            raise ValueError("allocate at least one card number")
        stmt = (
            update(Board)
            .where(Board.id == board_id, Board.org_id == self._org)
            .values(next_card_number=Board.next_card_number + n)
            .returning(Board.next_card_number)
        )
        end = (await self._db.execute(stmt)).scalar_one_or_none()
        if end is None:
            raise LookupError(f"board {board_id} not found")
        return range(end - n, end)
