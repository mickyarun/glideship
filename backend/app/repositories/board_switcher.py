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

"""The board switcher's groups, each filtered to visible boards in SQL."""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, not_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board import Board
from app.models.board_member import BoardUserPrefs
from app.repositories.board import BoardRepository, VisibleBoard
from app.repositories.board_access import PermissionChecker


@dataclass(frozen=True)
class SwitcherGroups:
    """Starred, recently opened, then every other board the caller can open."""

    starred: list[VisibleBoard]
    recent: list[VisibleBoard]
    other: list[VisibleBoard]


class BoardSwitcherRepository:
    """Switcher groups for one person in one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        self._boards = BoardRepository(db, org_id=org_id)

    async def groups(
        self,
        user_id: uuid.UUID,
        perms: PermissionChecker,
        *,
        q: str | None,
        recent_limit: int,
        other_limit: int,
    ) -> SwitcherGroups:
        """Each group in one query; ``q`` narrows all three by name or key."""
        base = self._boards.visible_select(user_id, perms, q=q)
        by_name = (func.lower(Board.name), Board.id)
        starred = await self._boards.run_visible(
            base.where(BoardUserPrefs.starred.is_(True)).order_by(*by_name)
        )
        not_starred = or_(BoardUserPrefs.starred.is_(None), not_(BoardUserPrefs.starred))
        recent = await self._boards.run_visible(
            base.where(not_starred, BoardUserPrefs.last_opened_at.is_not(None))
            .order_by(BoardUserPrefs.last_opened_at.desc(), Board.id)
            .limit(recent_limit)
        )
        shown = [b.board.id for b in recent]
        other_stmt = base.where(not_starred)
        if shown:
            other_stmt = other_stmt.where(Board.id.not_in(shown))
        other = await self._boards.run_visible(other_stmt.order_by(*by_name).limit(other_limit))
        return SwitcherGroups(starred=starred, recent=recent, other=other)
