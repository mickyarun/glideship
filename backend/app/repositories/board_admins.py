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

"""The admin rows that keep a board manageable, for the last-admin rule."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_enums import BoardMemberRole
from app.models.board_member import BoardMember, BoardTeam
from app.models.team import Team, TeamMember, TeamStatus
from app.models.user import User


@dataclass(frozen=True)
class AdminGrants:
    """The admin rows that count toward keeping a board manageable."""

    people: set[uuid.UUID]
    teams: set[uuid.UUID]

    @property
    def total(self) -> int:
        """How many rows count."""
        return len(self.people) + len(self.teams)


class BoardAdminRepository:
    """Board admin rows in one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        self._db = db
        self._org_id = org_id

    async def admin_grants(self, board_id: uuid.UUID) -> AdminGrants:
        """The admin rows that keep the board manageable, locked.

        A person's own row counts while they're active; a team's row counts
        while the team is active and has at least one active member. The
        rows are locked, so two removals can't each see the other's admin
        and leave the board with none.
        """
        people = (
            select(BoardMember.user_id)
            .join(User, User.id == BoardMember.user_id)
            .where(
                BoardMember.org_id == self._org_id,
                BoardMember.board_id == board_id,
                BoardMember.role == BoardMemberRole.ADMIN,
                User.is_active.is_(True),
            )
            .with_for_update(of=BoardMember)
        )
        staffed = (
            select(TeamMember.team_id)
            .join(User, User.id == TeamMember.user_id)
            .where(TeamMember.team_id == BoardTeam.team_id, User.is_active.is_(True))
            .exists()
        )
        teams = (
            select(BoardTeam.team_id)
            .join(Team, Team.id == BoardTeam.team_id)
            .where(
                BoardTeam.org_id == self._org_id,
                BoardTeam.board_id == board_id,
                BoardTeam.role == BoardMemberRole.ADMIN,
                Team.status == TeamStatus.ACTIVE,
                staffed,
            )
            .with_for_update(of=BoardTeam)
        )
        return AdminGrants(
            people=set((await self._db.execute(people)).scalars().all()),
            teams=set((await self._db.execute(teams)).scalars().all()),
        )
