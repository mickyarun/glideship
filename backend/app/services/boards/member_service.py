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

"""Who holds which role on a board, individually or through a team.

A board keeps at least one admin row (a person's or an active team's), so
it can always be managed without ``boards:manage``. Removing someone or
lowering their role asks their open sockets to re-check the board topic,
so a person who lost access stops getting its live updates.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_enums import BoardMemberRole
from app.repositories.board_admins import BoardAdminRepository
from app.repositories.board_member import BoardMemberRepository
from app.repositories.team import TeamRepository
from app.schemas.boards.member import (
    MemberRead,
    MembersRead,
    TeamGrantRead,
    TeamOption,
    TeamOptions,
)
from app.services.boards.access import BoardAccess
from app.services.boards.errors import BoardConflictError, BoardItemNotFoundError
from app.services.boards.live import BoardChanges, BoardSocketEvent

LAST_ADMIN = "A board needs at least one admin; make someone else admin first."


async def list_members(db: AsyncSession, access: BoardAccess) -> MembersRead:
    """Everyone with their own role on the board, and every team with one."""
    repo = BoardMemberRepository(db, org_id=access.org_id)
    members = await repo.list_members(access.board.id)
    teams = await repo.list_teams(access.board.id)
    return MembersRead(
        members=[MemberRead(**vars(m)) for m in members],
        teams=[TeamGrantRead(**vars(t)) for t in teams],
    )


async def _keep_an_admin(
    db: AsyncSession,
    access: BoardAccess,
    *,
    person: uuid.UUID | None = None,
    team: uuid.UUID | None = None,
) -> None:
    """Refuse a change that takes away the board's last admin row that counts.

    An admin row that doesn't count (an inactive person, an archived or
    empty team) can always go.
    """
    grants = await BoardAdminRepository(db, org_id=access.org_id).admin_grants(access.board.id)
    counted = person in grants.people or team in grants.teams
    if counted and grants.total <= 1:
        raise BoardConflictError(LAST_ADMIN)


async def put_member(
    db: AsyncSession, access: BoardAccess, user_id: uuid.UUID, role: BoardMemberRole
) -> MembersRead:
    """Give a person their own role on the board."""
    repo = BoardMemberRepository(db, org_id=access.org_id)
    if not await repo.is_active_member(user_id):
        raise BoardItemNotFoundError("Member not found.")
    current = await repo.member_role(access.board.id, user_id)
    if current is BoardMemberRole.ADMIN and role is not BoardMemberRole.ADMIN:
        await _keep_an_admin(db, access, person=user_id)
    await repo.put_member(access.board.id, user_id, role)
    changes = BoardChanges.of(access)
    if current is not None and not role.at_least(current):
        changes.recheck_access({user_id})
    return await _done(db, access, changes)


async def remove_member(db: AsyncSession, access: BoardAccess, user_id: uuid.UUID) -> MembersRead:
    """Take away a person's own role; any team role they hold still applies."""
    repo = BoardMemberRepository(db, org_id=access.org_id)
    current = await repo.member_role(access.board.id, user_id)
    if current is None:
        raise BoardItemNotFoundError("That person has no role of their own on this board.")
    await _keep_an_admin(db, access, person=user_id)
    await repo.remove_member(access.board.id, user_id)
    changes = BoardChanges.of(access)
    changes.recheck_access({user_id})
    return await _done(db, access, changes)


async def team_options(db: AsyncSession, access: BoardAccess) -> TeamOptions:
    """Every active team in the board's org, for giving one a role here."""
    rows = await TeamRepository(db, org_id=access.org_id).list_active_with_member_counts()
    return TeamOptions(
        items=[TeamOption(id=team.id, name=team.name, member_count=count) for team, count in rows]
    )


async def put_team(
    db: AsyncSession, access: BoardAccess, team_id: uuid.UUID, role: BoardMemberRole
) -> MembersRead:
    """Give every member of a team this role on the board."""
    repo = BoardMemberRepository(db, org_id=access.org_id)
    if not await repo.team_exists(team_id):
        raise BoardItemNotFoundError("Team not found.")
    current = await repo.team_role(access.board.id, team_id)
    if current is BoardMemberRole.ADMIN and role is not BoardMemberRole.ADMIN:
        await _keep_an_admin(db, access, team=team_id)
    await repo.put_team(access.board.id, team_id, role)
    changes = BoardChanges.of(access)
    if current is not None and not role.at_least(current):
        changes.recheck_access(await repo.team_member_ids(team_id))
    return await _done(db, access, changes)


async def remove_team(db: AsyncSession, access: BoardAccess, team_id: uuid.UUID) -> MembersRead:
    """Take away a team's role on the board."""
    repo = BoardMemberRepository(db, org_id=access.org_id)
    current = await repo.team_role(access.board.id, team_id)
    if current is None:
        raise BoardItemNotFoundError("That team has no role on this board.")
    await _keep_an_admin(db, access, team=team_id)
    await repo.remove_team(access.board.id, team_id)
    changes = BoardChanges.of(access)
    changes.recheck_access(await repo.team_member_ids(team_id))
    return await _done(db, access, changes)


async def _done(db: AsyncSession, access: BoardAccess, changes: BoardChanges) -> MembersRead:
    changes.emit(BoardSocketEvent.MEMBER_CHANGED)
    await changes.commit(db)
    return await list_members(db, access)
