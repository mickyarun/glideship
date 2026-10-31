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

"""The tracked repositories a board links: anyone on it sees them, admins change them.

Unlinking a repository clears it from the board's cards in the same
transaction and announces each card it changed.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tracked_repository import TrackedRepository
from app.repositories.board_card_summary import BoardCardSummaryRepository
from app.repositories.board_repo import BoardRepoRepository
from app.schemas.boards.repo import BoardRepoRead, BoardReposRead, RepoOption, RepoOptions
from app.services.boards.access import BoardAccess
from app.services.boards.constants import GITHUB_WEB_URL
from app.services.boards.errors import BoardItemNotFoundError
from app.services.boards.live import BoardChanges, BoardSocketEvent
from app.services.boards.reads import card_summary, summary_json

REPO_NOT_FOUND = "Repository not found."
REPO_NOT_LINKED = "This board doesn't link that repository."


def repo_read(repo: TrackedRepository) -> BoardRepoRead:
    """A tracked repository as the boards API shows it."""
    full_name = repo.github_repo_full_name
    url = f"{GITHUB_WEB_URL}/{full_name}" if full_name else None
    return BoardRepoRead(id=repo.id, name=repo.name, url=url)


async def list_repos(db: AsyncSession, access: BoardAccess) -> BoardReposRead:
    """The repositories the board links, by name."""
    repos = await BoardRepoRepository(db, org_id=access.org_id).list_linked(access.board.id)
    return BoardReposRead(items=[repo_read(repo) for repo in repos])


async def get_repo(db: AsyncSession, access: BoardAccess, repo_id: uuid.UUID) -> BoardRepoRead:
    """One repository the board links."""
    linked = await list_repos(db, access)
    found = next((repo for repo in linked.items if repo.id == repo_id), None)
    if found is None:
        raise BoardItemNotFoundError(REPO_NOT_LINKED)
    return found


async def repo_options(db: AsyncSession, access: BoardAccess) -> RepoOptions:
    """The org's active repositories, each marked when the board links it."""
    rows = await BoardRepoRepository(db, org_id=access.org_id).options(access.board.id)
    return RepoOptions(
        items=[RepoOption(**repo_read(repo).model_dump(), linked=linked) for repo, linked in rows]
    )


async def link_repo(db: AsyncSession, access: BoardAccess, repo_id: uuid.UUID) -> BoardReposRead:
    """Link one of the org's active repositories; linking it again changes nothing."""
    repos = BoardRepoRepository(db, org_id=access.org_id)
    if await repos.active_repo(repo_id) is None:
        raise BoardItemNotFoundError(REPO_NOT_FOUND)
    changes = BoardChanges.of(access)
    if await repos.link(access.board.id, repo_id):
        changes.emit(BoardSocketEvent.REPOS_CHANGED, repo_id=str(repo_id), linked=True)
    await changes.commit(db)
    return await list_repos(db, access)


async def unlink_repo(db: AsyncSession, access: BoardAccess, repo_id: uuid.UUID) -> BoardReposRead:
    """Unlink a repository, clearing it from every card on the board that names it."""
    board_id = access.board.id
    repos = BoardRepoRepository(db, org_id=access.org_id)
    if not await repos.hold_link(board_id, repo_id, exclusive=True):
        raise BoardItemNotFoundError(REPO_NOT_LINKED)
    card_ids = await repos.detach_cards(board_id, repo_id)
    await repos.unlink(board_id, repo_id)
    changes = BoardChanges.of(access)
    changes.emit(BoardSocketEvent.REPOS_CHANGED, repo_id=str(repo_id), linked=False)
    summaries = BoardCardSummaryRepository(db, org_id=access.org_id)
    for row in await summaries.summaries_by_ids(board_id, card_ids):
        summary = card_summary(access.board, row)
        changes.emit(BoardSocketEvent.CARD_UPDATED, card=summary_json(summary))
    await changes.commit(db)
    return await list_repos(db, access)
