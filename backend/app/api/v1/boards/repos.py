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

"""Tracked repositories a board links: anyone on it can see them, admins change them."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.boards._access import manage_repos, view_board
from app.core.deps import get_db
from app.schemas.boards.repo import BoardRepoRead, BoardReposRead, RepoOptions
from app.services.boards import repo_service
from app.services.boards.access import BoardAccess

router = APIRouter(tags=["boards"])


@router.get("/{key}/repos", response_model=BoardReposRead)
async def list_repos(
    access: BoardAccess = Depends(view_board), db: AsyncSession = Depends(get_db)
) -> BoardReposRead:
    """The repositories the board links, by name."""
    return await repo_service.list_repos(db, access)


# Before /{repo_id}, which would otherwise try to read "options" as an id.
@router.get("/{key}/repos/options", response_model=RepoOptions)
async def list_repo_options(
    access: BoardAccess = Depends(manage_repos), db: AsyncSession = Depends(get_db)
) -> RepoOptions:
    """The org's active repositories a board admin can link."""
    return await repo_service.repo_options(db, access)


@router.get("/{key}/repos/{repo_id}", response_model=BoardRepoRead)
async def get_repo(
    repo_id: uuid.UUID,
    access: BoardAccess = Depends(view_board),
    db: AsyncSession = Depends(get_db),
) -> BoardRepoRead:
    """One repository the board links."""
    return await repo_service.get_repo(db, access, repo_id)


@router.put("/{key}/repos/{repo_id}", response_model=BoardReposRead)
async def link_repo(
    repo_id: uuid.UUID,
    access: BoardAccess = Depends(manage_repos),
    db: AsyncSession = Depends(get_db),
) -> BoardReposRead:
    """Link one of the org's active repositories to the board."""
    return await repo_service.link_repo(db, access, repo_id)


@router.delete("/{key}/repos/{repo_id}", response_model=BoardReposRead)
async def unlink_repo(
    repo_id: uuid.UUID,
    access: BoardAccess = Depends(manage_repos),
    db: AsyncSession = Depends(get_db),
) -> BoardReposRead:
    """Unlink a repository; cards that named it lose their repository."""
    return await repo_service.unlink_repo(db, access, repo_id)
