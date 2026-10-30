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

"""People and teams on a board: anyone on it can see them, admins change them."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.boards._access import manage_members, view_board
from app.core.deps import get_db
from app.schemas.boards.member import MembersRead, RoleBody, TeamOptions
from app.services.boards import member_service
from app.services.boards.access import BoardAccess

router = APIRouter(tags=["boards"])


@router.get("/{key}/members", response_model=MembersRead)
async def list_members(
    access: BoardAccess = Depends(view_board), db: AsyncSession = Depends(get_db)
) -> MembersRead:
    """Everyone with a role of their own, and every team with one."""
    return await member_service.list_members(db, access)


@router.put("/{key}/members/{user_id}", response_model=MembersRead)
async def put_member(
    user_id: uuid.UUID,
    body: RoleBody,
    access: BoardAccess = Depends(manage_members),
    db: AsyncSession = Depends(get_db),
) -> MembersRead:
    """Give a person a role of their own on the board."""
    return await member_service.put_member(db, access, user_id, body.role)


@router.delete("/{key}/members/{user_id}", response_model=MembersRead)
async def remove_member(
    user_id: uuid.UUID,
    access: BoardAccess = Depends(manage_members),
    db: AsyncSession = Depends(get_db),
) -> MembersRead:
    """Take away a person's own role on the board."""
    return await member_service.remove_member(db, access, user_id)


@router.get("/{key}/teams/options", response_model=TeamOptions)
async def list_team_options(
    access: BoardAccess = Depends(manage_members), db: AsyncSession = Depends(get_db)
) -> TeamOptions:
    """The org's teams a board admin can give a role, with their sizes."""
    return await member_service.team_options(db, access)


@router.put("/{key}/teams/{team_id}", response_model=MembersRead)
async def put_team(
    team_id: uuid.UUID,
    body: RoleBody,
    access: BoardAccess = Depends(manage_members),
    db: AsyncSession = Depends(get_db),
) -> MembersRead:
    """Give a team a role on the board."""
    return await member_service.put_team(db, access, team_id, body.role)


@router.delete("/{key}/teams/{team_id}", response_model=MembersRead)
async def remove_team(
    team_id: uuid.UUID,
    access: BoardAccess = Depends(manage_members),
    db: AsyncSession = Depends(get_db),
) -> MembersRead:
    """Take away a team's role on the board."""
    return await member_service.remove_team(db, access, team_id)
