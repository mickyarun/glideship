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

"""Data access for the people and teams holding a role on a board."""

import uuid
from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_enums import BoardMemberRole
from app.models.board_member import BoardMember, BoardTeam
from app.models.team import Team, TeamMember
from app.models.user import OrgToUser, User
from app.repositories.base import rowcount


@dataclass(frozen=True)
class MemberRow:
    """A person's own role on a board."""

    user_id: uuid.UUID
    name: str
    avatar_url: str | None
    role: BoardMemberRole


@dataclass(frozen=True)
class TeamRow:
    """A team's role on a board."""

    team_id: uuid.UUID
    name: str
    role: BoardMemberRole


class BoardMemberRepository:
    """Individual and team roles on boards in one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        self._db = db
        self._org_id = org_id

    async def list_members(self, board_id: uuid.UUID) -> list[MemberRow]:
        """People with their own row on the board, by name."""
        stmt = (
            select(BoardMember.user_id, User.name, User.avatar_url, BoardMember.role)
            .join(User, User.id == BoardMember.user_id)
            .where(BoardMember.org_id == self._org_id, BoardMember.board_id == board_id)
            .order_by(func.lower(User.name), BoardMember.user_id)
        )
        return [MemberRow(*row) for row in (await self._db.execute(stmt)).all()]

    async def list_teams(self, board_id: uuid.UUID) -> list[TeamRow]:
        """Teams holding a role on the board, by name."""
        stmt = (
            select(BoardTeam.team_id, Team.name, BoardTeam.role)
            .join(Team, Team.id == BoardTeam.team_id)
            .where(BoardTeam.org_id == self._org_id, BoardTeam.board_id == board_id)
            .order_by(func.lower(Team.name), BoardTeam.team_id)
        )
        return [TeamRow(*row) for row in (await self._db.execute(stmt)).all()]

    async def member_role(self, board_id: uuid.UUID, user_id: uuid.UUID) -> BoardMemberRole | None:
        """A person's own row on the board, if they have one."""
        stmt = select(BoardMember.role).where(
            BoardMember.org_id == self._org_id,
            BoardMember.board_id == board_id,
            BoardMember.user_id == user_id,
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def team_role(self, board_id: uuid.UUID, team_id: uuid.UUID) -> BoardMemberRole | None:
        """A team's row on the board, if it has one."""
        stmt = select(BoardTeam.role).where(
            BoardTeam.org_id == self._org_id,
            BoardTeam.board_id == board_id,
            BoardTeam.team_id == team_id,
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def put_member(
        self, board_id: uuid.UUID, user_id: uuid.UUID, role: BoardMemberRole
    ) -> None:
        """Give a person this role on the board, replacing any they had."""
        stmt = insert(BoardMember).values(
            board_id=board_id, user_id=user_id, org_id=self._org_id, role=role
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_board_members_board_user", set_={"role": role}
        )
        await self._db.execute(stmt)

    async def put_team(
        self, board_id: uuid.UUID, team_id: uuid.UUID, role: BoardMemberRole
    ) -> None:
        """Give a team this role on the board, replacing any it had."""
        stmt = insert(BoardTeam).values(
            board_id=board_id, team_id=team_id, org_id=self._org_id, role=role
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_board_teams_board_team", set_={"role": role}
        )
        await self._db.execute(stmt)

    async def remove_member(self, board_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Drop a person's own row; False when there was none."""
        stmt = delete(BoardMember).where(
            BoardMember.org_id == self._org_id,
            BoardMember.board_id == board_id,
            BoardMember.user_id == user_id,
        )
        return rowcount(await self._db.execute(stmt)) > 0

    async def remove_team(self, board_id: uuid.UUID, team_id: uuid.UUID) -> bool:
        """Drop a team's row; False when there was none."""
        stmt = delete(BoardTeam).where(
            BoardTeam.org_id == self._org_id,
            BoardTeam.board_id == board_id,
            BoardTeam.team_id == team_id,
        )
        return rowcount(await self._db.execute(stmt)) > 0

    async def is_active_member(self, user_id: uuid.UUID) -> bool:
        """Whether ``user_id`` is an active member of the org."""
        stmt = (
            select(OrgToUser.user_id)
            .join(User, User.id == OrgToUser.user_id)
            .where(
                OrgToUser.org_id == self._org_id,
                OrgToUser.user_id == user_id,
                User.is_active.is_(True),
            )
        )
        return (await self._db.execute(stmt)).first() is not None

    async def team_exists(self, team_id: uuid.UUID) -> bool:
        """Whether the team belongs to the org."""
        stmt = select(Team.id).where(Team.org_id == self._org_id, Team.id == team_id)
        return (await self._db.execute(stmt)).first() is not None

    async def team_member_ids(self, team_id: uuid.UUID) -> set[uuid.UUID]:
        """Everyone in the team."""
        stmt = select(TeamMember.user_id).where(
            TeamMember.org_id == self._org_id, TeamMember.team_id == team_id
        )
        return set((await self._db.execute(stmt)).scalars().all())
