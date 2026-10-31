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

from sqlalchemy import (
    CTE,
    ColumnElement,
    Subquery,
    and_,
    cast,
    func,
    literal,
    select,
    union_all,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions_boards import BOARDS_MANAGE, BOARDS_VIEW
from app.models.board import Board
from app.models.board_enums import BoardMemberRole, BoardStatus, BoardVisibility
from app.models.board_member import BoardMember, BoardTeam
from app.models.team import Team, TeamMember, TeamStatus
from app.models.user import OrgToUser, User
from app.repositories.membership_predicates import membership_holds

_ROLE_TYPE = BoardMember.__table__.c.role.type


class PermissionChecker(Protocol):
    """Anything that answers whether its holder has an org permission."""

    def has(self, permission: str) -> bool:
        """Return True if the holder has ``permission``."""
        ...


def _role(role: BoardMemberRole) -> ColumnElement[BoardMemberRole]:
    return cast(literal(role.value), _ROLE_TYPE)


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
        rows = self._roles(grants, name)
        return select(rows.c.board_id, rows.c.role).subquery(name)

    async def role_for(
        self, board_id: uuid.UUID, user_id: uuid.UUID, perms: PermissionChecker
    ) -> BoardMemberRole | None:
        """The caller's role on one board, or None when they have none."""
        roles = self.role_subquery(user_id, perms)
        stmt = select(roles.c.role).where(roles.c.board_id == board_id)
        return (await self._db.execute(stmt)).scalar_one_or_none()

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
                roles.c.role == _role(BoardMemberRole.ADMIN), Board.status == BoardStatus.ACTIVE
            )
            .limit(1)
        )
        return (await self._db.execute(stmt)).first() is not None

    async def users_with_access(
        self, board_id: uuid.UUID, user_ids: set[uuid.UUID]
    ) -> set[uuid.UUID]:
        """Which of ``user_ids`` are active members holding any role on the board."""
        if not user_ids:
            return set()
        grants = (
            select(
                OrgToUser.user_id.label("user_id"),
                membership_holds(BOARDS_VIEW).label("can_view"),
                membership_holds(BOARDS_MANAGE).label("can_manage"),
            )
            .join(User, User.id == OrgToUser.user_id)
            .where(
                OrgToUser.org_id == self._org_id,
                OrgToUser.user_id.in_(user_ids),
                User.is_active.is_(True),
            )
            .cte("board_grants")
        )
        rows = self._roles(grants, "board_roles")
        stmt = select(rows.c.user_id).where(rows.c.board_id == board_id)
        return set((await self._db.execute(stmt)).scalars().all())

    def _roles(self, grants: CTE, name: str) -> Subquery:
        """``(user_id, board_id, role)``: the highest role per person and board.

        ``grants`` has one row per person: ``user_id``, ``can_view``
        (holds ``boards:view``) and ``can_manage`` (holds ``boards:manage``).
        """
        org_boards = Board.org_id == self._org_id
        manage = (
            select(
                grants.c.user_id,
                Board.id.label("board_id"),
                _role(BoardMemberRole.ADMIN).label("role"),
            )
            .select_from(grants)
            .join(Board, org_boards)
            # boards:manage widens boards:view; on its own it opens nothing.
            .where(grants.c.can_manage, grants.c.can_view)
        )
        members = (
            select(BoardMember.user_id, BoardMember.board_id, BoardMember.role)
            .join(grants, grants.c.user_id == BoardMember.user_id)
            .where(BoardMember.org_id == self._org_id, grants.c.can_view)
        )
        teams = (
            select(TeamMember.user_id, BoardTeam.board_id, BoardTeam.role)
            .select_from(BoardTeam)
            .join(TeamMember, TeamMember.team_id == BoardTeam.team_id)
            .join(Team, Team.id == BoardTeam.team_id)
            .join(grants, grants.c.user_id == TeamMember.user_id)
            .where(
                BoardTeam.org_id == self._org_id,
                Team.status == TeamStatus.ACTIVE,
                grants.c.can_view,
            )
        )
        org_visible = (
            select(grants.c.user_id, Board.id, _role(BoardMemberRole.VIEWER))
            .select_from(grants)
            .join(Board, and_(org_boards, Board.visibility == BoardVisibility.ORG))
            .where(grants.c.can_view)
        )
        rows = union_all(manage, members, teams, org_visible).subquery(f"{name}_rows")
        return (
            select(rows.c.user_id, rows.c.board_id, func.max(rows.c.role).label("role"))
            .group_by(rows.c.user_id, rows.c.board_id)
            .subquery(f"{name}_max")
        )
