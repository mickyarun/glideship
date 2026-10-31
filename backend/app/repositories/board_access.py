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

"""The one rule for who holds which role on a board, written once in SQL.

A person's role on a board is the highest of:

1. ``admin`` when they hold ``boards:manage``;
2. their own ``board_members`` row, when they hold ``boards:view``;
3. the ``board_teams`` row of every active team they belong to, when they
   hold ``boards:view``;
4. ``viewer`` when the board is visible to the whole org and they hold
   ``boards:view``.

Anyone else has no role, and the API answers 404 so members-only boards
don't leak. Postgres orders enum values as declared, so ``max(role)``
picks the highest. Every caller (board lists, the by-key lookup, socket
subscriptions, notification recipients) goes through these queries.
"""

import uuid
from typing import Protocol

from sqlalchemy import Subquery, literal, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions_boards import BOARDS_MANAGE, BOARDS_VIEW
from app.models.board import Board
from app.models.board_enums import BoardMemberRole, BoardStatus
from app.repositories.board_role_rows import highest_roles, member_grants, role_literal


class PermissionChecker(Protocol):
    """Anything that answers whether its holder has an org permission."""

    def has(self, permission: str) -> bool:
        """Return True if the holder has ``permission``."""
        ...


class BoardAccessRepository:
    """Board roles for people in one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        self._db = db
        self._org_id = org_id

    def role_subquery(
        self, user_id: uuid.UUID, perms: PermissionChecker, *, name: str = "board_roles"
    ) -> Subquery:
        """``(board_id, role)`` for every board in the org where ``user_id`` has a role.

        ``name`` aliases the subquery and its CTE, so two can share a statement.
        """
        grants = select(
            literal(user_id, UUID(as_uuid=True)).label("user_id"),
            literal(perms.has(BOARDS_VIEW)).label("can_view"),
            literal(perms.has(BOARDS_MANAGE)).label("can_manage"),
        ).cte(f"{name}_grants")
        rows = highest_roles(self._org_id, grants, name)
        return select(rows.c.board_id, rows.c.role).subquery(name)

    async def role_for(
        self, board_id: uuid.UUID, user_id: uuid.UUID, perms: PermissionChecker
    ) -> BoardMemberRole | None:
        """The caller's role on one board, or None when they have none."""
        roles = self.role_subquery(user_id, perms)
        stmt = select(roles.c.role).where(roles.c.board_id == board_id)
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def boards_with_role(
        self, board_ids: set[uuid.UUID], user_id: uuid.UUID, perms: PermissionChecker
    ) -> set[uuid.UUID]:
        """Which of ``board_ids`` the caller holds any role on, in one query."""
        if not board_ids:
            return set()
        roles = self.role_subquery(user_id, perms)
        stmt = select(roles.c.board_id).where(roles.c.board_id.in_(board_ids))
        return set((await self._db.execute(stmt)).scalars().all())

    async def board_with_role(
        self, key: str, user_id: uuid.UUID, perms: PermissionChecker
    ) -> tuple[Board, BoardMemberRole] | None:
        """The board with this key and the caller's role on it, if they have one."""
        roles = self.role_subquery(user_id, perms)
        stmt = (
            select(Board, roles.c.role)
            .join(roles, roles.c.board_id == Board.id)
            .where(Board.org_id == self._org_id, Board.key == key)
        )
        row = (await self._db.execute(stmt)).one_or_none()
        return None if row is None else (row[0], row[1])

    async def administers_any(self, user_id: uuid.UUID, perms: PermissionChecker) -> bool:
        """Whether the caller is admin on at least one active board in the org."""
        roles = self.role_subquery(user_id, perms)
        stmt = (
            select(roles.c.board_id)
            .join(Board, Board.id == roles.c.board_id)
            .where(
                roles.c.role == role_literal(BoardMemberRole.ADMIN),
                Board.status == BoardStatus.ACTIVE,
            )
            .limit(1)
        )
        return (await self._db.execute(stmt)).first() is not None

    async def users_with_access(
        self,
        board_id: uuid.UUID,
        user_ids: set[uuid.UUID],
        *,
        min_role: BoardMemberRole = BoardMemberRole.VIEWER,
    ) -> set[uuid.UUID]:
        """Which of ``user_ids`` are active members holding ``min_role`` or more on the board."""
        if not user_ids:
            return set()
        grants = member_grants(self._org_id, user_ids, "board_grants")
        rows = highest_roles(self._org_id, grants, "board_roles")
        stmt = select(rows.c.user_id).where(rows.c.board_id == board_id)
        if min_role is not BoardMemberRole.VIEWER:
            stmt = stmt.where(rows.c.role >= role_literal(min_role))
        return set((await self._db.execute(stmt)).scalars().all())

    async def access_pairs(
        self, board_ids: set[uuid.UUID], user_ids: set[uuid.UUID]
    ) -> set[tuple[uuid.UUID, uuid.UUID]]:
        """``(board_id, user_id)`` for each of ``user_ids`` with a role on each of ``board_ids``.

        :meth:`users_with_access` for many boards at once, in one query.
        """
        if not board_ids or not user_ids:
            return set()
        grants = member_grants(self._org_id, user_ids, "pair_grants")
        rows = highest_roles(self._org_id, grants, "pair_roles")
        stmt = select(rows.c.board_id, rows.c.user_id).where(rows.c.board_id.in_(board_ids))
        return {(row[0], row[1]) for row in (await self._db.execute(stmt)).all()}
