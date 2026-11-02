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

"""Data access for board stages, scoped to an organization.

Changes to a board's stage set lock every stage row of the board first
(:meth:`lock_board_stages`), so two admins editing stages at once can't
both pass the rule checks; card writes lock just the stage they land in.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board import BoardStage
from app.models.board_card import BoardCard
from app.repositories.base import BaseRepository, violated_constraint

_UNIQUE_NAME = "uq_board_stages_board_name"


class BoardStageRepository(BaseRepository[BoardStage]):
    """Tenant-scoped repository for board stages."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        super().__init__(BoardStage, db, org_id=org_id)

    async def list_for_board(self, board_id: uuid.UUID) -> list[BoardStage]:
        """The board's stages, left to right."""
        stmt = self._scoped(
            select(BoardStage)
            .where(BoardStage.board_id == board_id)
            .order_by(BoardStage.position, BoardStage.id)
        )
        return list((await self._db.execute(stmt)).scalars().all())

    async def lock_board_stages(self, board_id: uuid.UUID) -> list[BoardStage]:
        """Every stage of the board, locked until the transaction ends.

        Locked in id order so concurrent callers never deadlock.
        """
        stmt = self._scoped(
            select(BoardStage)
            .where(BoardStage.board_id == board_id)
            .order_by(BoardStage.id)
            .with_for_update()
        )
        stages = list((await self._db.execute(stmt)).scalars().all())
        return sorted(stages, key=lambda s: (s.position, str(s.id)))

    async def get_in_board(self, board_id: uuid.UUID, stage_id: uuid.UUID) -> BoardStage | None:
        """One stage, or None when it isn't on this board."""
        stmt = self._scoped(
            select(BoardStage).where(BoardStage.id == stage_id, BoardStage.board_id == board_id)
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def lock(self, board_id: uuid.UUID, stage_id: uuid.UUID) -> BoardStage | None:
        """One stage of the board, locked until the transaction ends.

        Every card write into a stage takes this lock first, so positions
        computed from the stage's cards can't race. A stage already loaded
        in the session is re-read, so its rules are the locked ones.
        """
        stmt = self._scoped(
            select(BoardStage)
            .where(BoardStage.id == stage_id, BoardStage.board_id == board_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def lock_stages(
        self, board_id: uuid.UUID, stage_ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, BoardStage]:
        """These stages of the board, locked in id order (the order every writer uses)."""
        stmt = self._scoped(
            select(BoardStage)
            .where(BoardStage.board_id == board_id, BoardStage.id.in_(stage_ids))
            .order_by(BoardStage.id)
            .with_for_update()
        )
        return {s.id: s for s in (await self._db.execute(stmt)).scalars().all()}

    async def default_stage(self, board_id: uuid.UUID) -> BoardStage | None:
        """Where new cards land, locked like :meth:`lock`."""
        stmt = self._scoped(
            select(BoardStage)
            .where(BoardStage.board_id == board_id, BoardStage.is_default.is_(True))
            .with_for_update()
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def save(self) -> bool:
        """Flush stage edits; False when a stage name clashes on the board."""
        try:
            async with self._db.begin_nested():
                await self._db.flush()
        except IntegrityError as exc:
            if violated_constraint(exc) == _UNIQUE_NAME:
                return False
            raise
        return True

    async def open_card_counts(self, board_id: uuid.UUID) -> dict[uuid.UUID, int]:
        """Open (unarchived) cards per stage; stages with none are absent."""
        stmt = (
            select(BoardCard.stage_id, func.count())
            .where(
                BoardCard.org_id == self._org_id,
                BoardCard.board_id == board_id,
                BoardCard.archived_at.is_(None),
            )
            .group_by(BoardCard.stage_id)
        )
        return {row[0]: row[1] for row in (await self._db.execute(stmt)).all()}
