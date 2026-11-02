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

"""Data access for board labels, scoped to an organization."""

import uuid
from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board import BoardLabel
from app.repositories.base import BaseRepository, violated_constraint

_UNIQUE_NAME = "uq_board_labels_board_name"


class BoardLabelRepository(BaseRepository[BoardLabel]):
    """Tenant-scoped repository for board labels."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        super().__init__(BoardLabel, db, org_id=org_id)

    async def list_for_board(self, board_id: uuid.UUID) -> list[BoardLabel]:
        """The board's labels, by name."""
        stmt = self._scoped(
            select(BoardLabel)
            .where(BoardLabel.board_id == board_id)
            .order_by(func.lower(BoardLabel.name), BoardLabel.id)
        )
        return list((await self._db.execute(stmt)).scalars().all())

    async def get_in_board(self, board_id: uuid.UUID, label_id: uuid.UUID) -> BoardLabel | None:
        """One label, or None when it isn't on this board."""
        stmt = self._scoped(
            select(BoardLabel).where(BoardLabel.id == label_id, BoardLabel.board_id == board_id)
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def hold_labels(self, board_id: uuid.UUID, ids: Iterable[uuid.UUID]) -> set[uuid.UUID]:
        """Which of ``ids`` are labels on this board, held ``FOR KEY SHARE`` until commit.

        A card write that names labels holds them first, so none can be
        deleted between the check and the write (a key-share lock blocks a
        delete, not a rename). One deleted before the hold is simply left out.
        """
        wanted = set(ids)
        if not wanted:
            return set()
        stmt = self._scoped(
            select(BoardLabel.id)
            .where(BoardLabel.board_id == board_id, BoardLabel.id.in_(wanted))
            .order_by(BoardLabel.id)
            .with_for_update(read=True, key_share=True)
        )
        return set((await self._db.execute(stmt)).scalars().all())

    async def save(self, label: BoardLabel) -> bool:
        """Add or flush a label; False when its name is taken on the board."""
        try:
            async with self._db.begin_nested():
                self._db.add(label)
                await self._db.flush()
        except IntegrityError as exc:
            if violated_constraint(exc) == _UNIQUE_NAME:
                return False
            raise
        await self._db.refresh(label)
        return True
