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

"""The SQL pieces of the board role rule, shared by every query that applies it.

:func:`role_rows` lists every grant a person holds on each board, tagged
with where it comes from; :func:`highest_roles` keeps the highest per
person and board. :mod:`app.repositories.board_access` documents the rule.
"""

import uuid

from sqlalchemy import CTE, ColumnElement, Subquery, and_, cast, func, literal, select, union_all

from app.core.permissions_boards import BOARDS_MANAGE, BOARDS_VIEW
from app.models.board import Board
from app.models.board_enums import BoardAccessVia, BoardMemberRole, BoardVisibility
from app.models.board_member import BoardMember, BoardTeam
from app.models.team import Team, TeamMember, TeamStatus
from app.models.user import OrgToUser, User
from app.repositories.membership_predicates import membership_holds

_ROLE_TYPE = BoardMember.__table__.c.role.type


def role_literal(role: BoardMemberRole) -> ColumnElement[BoardMemberRole]:
    """``role`` as a ``board_member_role`` value, so it compares and sorts as one."""
    return cast(literal(role.value), _ROLE_TYPE)


def _via(via: BoardAccessVia) -> ColumnElement[str]:
    return literal(via.value).label("via")


def member_grants(org_id: uuid.UUID, user_ids: set[uuid.UUID] | None, name: str) -> CTE:
    """One grants row per active member of the org (only ``user_ids`` when given)."""
    stmt = (
        select(
            OrgToUser.user_id.label("user_id"),
            membership_holds(BOARDS_VIEW).label("can_view"),
            membership_holds(BOARDS_MANAGE).label("can_manage"),
        )
        .join(User, User.id == OrgToUser.user_id)
        .where(OrgToUser.org_id == org_id, User.is_active.is_(True))
    )
    if user_ids is not None:
        stmt = stmt.where(OrgToUser.user_id.in_(user_ids))
    return stmt.cte(name)


def role_rows(org_id: uuid.UUID, grants: CTE, name: str) -> Subquery:
    """``(user_id, board_id, role, via)``: every grant, before taking the highest.

    ``grants`` has one row per person: ``user_id``, ``can_view`` (holds
    ``boards:view``) and ``can_manage`` (holds ``boards:manage``).
    """
    org_boards = Board.org_id == org_id
    manage = (
        select(
            grants.c.user_id,
            Board.id.label("board_id"),
            role_literal(BoardMemberRole.ADMIN).label("role"),
            _via(BoardAccessVia.ORG),
        )
        .select_from(grants)
        .join(Board, org_boards)
        # boards:manage widens boards:view; on its own it opens nothing.
        .where(grants.c.can_manage, grants.c.can_view)
    )
    members = (
        select(
            BoardMember.user_id,
            BoardMember.board_id,
            BoardMember.role,
            _via(BoardAccessVia.MEMBER),
        )
        .join(grants, grants.c.user_id == BoardMember.user_id)
        .where(BoardMember.org_id == org_id, grants.c.can_view)
    )
    teams = (
        select(TeamMember.user_id, BoardTeam.board_id, BoardTeam.role, _via(BoardAccessVia.TEAM))
        .select_from(BoardTeam)
        .join(TeamMember, TeamMember.team_id == BoardTeam.team_id)
        .join(Team, Team.id == BoardTeam.team_id)
        .join(grants, grants.c.user_id == TeamMember.user_id)
        .where(BoardTeam.org_id == org_id, Team.status == TeamStatus.ACTIVE, grants.c.can_view)
    )
    org_visible = (
        select(
            grants.c.user_id,
            Board.id,
            role_literal(BoardMemberRole.VIEWER),
            _via(BoardAccessVia.ORG),
        )
        .select_from(grants)
        .join(Board, and_(org_boards, Board.visibility == BoardVisibility.ORG))
        .where(grants.c.can_view)
    )
    return union_all(manage, members, teams, org_visible).subquery(f"{name}_rows")


def highest_roles(org_id: uuid.UUID, grants: CTE, name: str) -> Subquery:
    """``(user_id, board_id, role)``: the highest role per person and board."""
    rows = role_rows(org_id, grants, name)
    return (
        select(rows.c.user_id, rows.c.board_id, func.max(rows.c.role).label("role"))
        .group_by(rows.c.user_id, rows.c.board_id)
        .subquery(f"{name}_max")
    )
