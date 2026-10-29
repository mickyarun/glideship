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

"""Data access for boards, scoped to an organization.

Lists only ever return boards the caller holds a role on, joined to
:meth:`BoardAccessRepository.role_subquery` in SQL; nothing is fetched
first and filtered afterwards.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board import Board
from app.models.board_enums import BoardMemberRole, BoardStatus
from app.models.board_member import BoardUserPrefs
from app.repositories.base import BaseRepository, violated_constraint
from app.repositories.board_access import BoardAccessRepository, PermissionChecker

_UNIQUE_KEY_OR_NAME = frozenset({"uq_boards_org_key", "uq_boards_org_name"})


@dataclass(frozen=True)
class VisibleBoard:
    """A board the caller can open, their role on it and their prefs for it."""

    board: Board
    role: BoardMemberRole
    starred: bool
    last_opened_at: datetime | None


def like_pattern(text: str) -> str:
    """An ILIKE pattern matching ``text`` anywhere, with wildcards escaped."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class BoardRepository(BaseRepository[Board]):
    """Tenant-scoped repository for boards."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        super().__init__(Board, db, org_id=org_id)
        self._org: uuid.UUID = org_id

    def visible_select(
        self, user_id: uuid.UUID, perms: PermissionChecker, *, q: str | None = None
    ) -> Select[tuple[Board, BoardMemberRole, Any, Any]]:
        """Active boards the caller holds a role on, with their star and last visit.

        ``q`` narrows to boards whose name or key contains it.
        """
        roles = BoardAccessRepository(self._db, org_id=self._org).role_subquery(user_id, perms)
        stmt = (
            select(Board, roles.c.role, BoardUserPrefs.starred, BoardUserPrefs.last_opened_at)
            .join(roles, roles.c.board_id == Board.id)
            .outerjoin(
                BoardUserPrefs,
                and_(BoardUserPrefs.board_id == Board.id, BoardUserPrefs.user_id == user_id),
            )
            .where(Board.org_id == self._org, Board.status == BoardStatus.ACTIVE)
        )
        if q:
            pattern = like_pattern(q)
            stmt = stmt.where(or_(Board.name.ilike(pattern), Board.key.ilike(pattern)))
        return stmt

    async def run_visible(
        self, stmt: Select[tuple[Board, BoardMemberRole, Any, Any]]
    ) -> list[VisibleBoard]:
        """Execute a :meth:`visible_select` statement."""
        rows = (await self._db.execute(stmt)).all()
        return [VisibleBoard(r[0], r[1], bool(r[2]), r[3]) for r in rows]

    async def list_visible(
        self, user_id: uuid.UUID, perms: PermissionChecker
    ) -> list[VisibleBoard]:
        """Every active board the caller can open, by name."""
        stmt = self.visible_select(user_id, perms).order_by(func.lower(Board.name), Board.id)
        return await self.run_visible(stmt)

    async def any_visible(self, user_id: uuid.UUID, perms: PermissionChecker) -> bool:
        """Whether the caller can open at least one active board."""
        visible = self.visible_select(user_id, perms).with_only_columns(Board.id)
        stmt = select(visible.exists())
        return bool((await self._db.execute(stmt)).scalar())

    async def key_or_name_taken(
        self, *, key: str | None = None, name: str | None = None, exclude: uuid.UUID | None = None
    ) -> bool:
        """Whether any board in the org, visible or not, uses this key or name.

        Names compare case-insensitively, so "Ops" and "ops" can't both exist.
        """
        clauses = []
        if key is not None:
            clauses.append(Board.key == key)
        if name is not None:
            clauses.append(func.lower(Board.name) == name.lower())
        if not clauses:
            return False
        stmt = select(Board.id).where(Board.org_id == self._org, or_(*clauses))
        if exclude is not None:
            stmt = stmt.where(Board.id != exclude)
        return (await self._db.execute(stmt.limit(1))).first() is not None

    async def insert(self, board: Board) -> bool:
        """Add a board; False when another board took its key or name first."""
        try:
            async with self._db.begin_nested():
                self._db.add(board)
                await self._db.flush()
        except IntegrityError as exc:
            if violated_constraint(exc) in _UNIQUE_KEY_OR_NAME:
                return False
            raise
        return True

    async def save(self, board: Board) -> bool:
        """Flush edits to a board; False when its new name is already taken."""
        try:
            async with self._db.begin_nested():
                await self._db.flush()
        except IntegrityError as exc:
            if violated_constraint(exc) in _UNIQUE_KEY_OR_NAME:
                return False
            raise
        await self._db.refresh(board)
        return True
