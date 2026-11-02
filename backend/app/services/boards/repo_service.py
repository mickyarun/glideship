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
transaction and announces it once, with how many cards it cleared;
clients clear the repository from the cards they hold. A repository that
is ignored or removed in settings is unlinked from every board the same way.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tracked_repository import TrackedRepository
from app.repositories.board_repo import BoardRepoRepository
from app.schemas.boards.repo import BoardRepoRead, BoardReposRead, RepoOption, RepoOptions
from app.services.boards.access import BoardAccess
from app.services.boards.constants import GITHUB_FULL_NAME_PATTERN, GITHUB_WEB_URL
from app.services.boards.errors import BoardItemNotFoundError
from app.services.boards.live import BoardChanges, BoardSocketEvent

REPO_NOT_FOUND = "Repository not found."
REPO_NOT_LINKED = "This board doesn't link that repository."


def repo_read(repo: TrackedRepository) -> BoardRepoRead:
    """A tracked repository as the boards API shows it."""
    full_name = repo.github_repo_full_name
    named = full_name is not None and GITHUB_FULL_NAME_PATTERN.fullmatch(full_name)
    url = f"{GITHUB_WEB_URL}/{full_name}" if named else None
    return BoardRepoRead(id=repo.id, name=repo.name, url=url)


async def list_repos(db: AsyncSession, access: BoardAccess) -> BoardReposRead:
    """The active repositories the board links, by name."""
    repos = await BoardRepoRepository(db, org_id=access.org_id).list_linked(access.board.id)
    return BoardReposRead(items=[repo_read(repo) for repo in repos])


async def get_repo(db: AsyncSession, access: BoardAccess, repo_id: uuid.UUID) -> BoardRepoRead:
    """One active repository the board links."""
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
    repo = await repos.active_repo(repo_id)
    if repo is None:
        raise BoardItemNotFoundError(REPO_NOT_FOUND)
    changes = BoardChanges.of(access)
    if await repos.link(access.board.id, repo_id):
        changes.emit(
            BoardSocketEvent.REPOS_CHANGED,
            repo_id=str(repo_id),
            linked=True,
            repo=repo_read(repo).model_dump(mode="json"),
        )
    await changes.commit(db)
    return await list_repos(db, access)


async def unlink_repo(db: AsyncSession, access: BoardAccess, repo_id: uuid.UUID) -> BoardReposRead:
    """Unlink a repository, clearing it from every card on the board that names it.

    Works whatever the repository's status, so an admin can always remove a link.
    """
    board_id = access.board.id
    repos = BoardRepoRepository(db, org_id=access.org_id)
    if not await repos.take_link(board_id, repo_id):
        raise BoardItemNotFoundError(REPO_NOT_LINKED)
    changes = BoardChanges.of(access)
    await _detach(repos, changes, repo_id)
    await changes.commit(db)
    return await list_repos(db, access)


async def unlink_retired_repo(
    db: AsyncSession, *, org_id: uuid.UUID, repo_id: uuid.UUID, actor_id: uuid.UUID
) -> None:
    """Unlink a repository that stopped being active from every board, as an admin would.

    Call it in the transaction that changes the repository's status; each
    board hears ``repos_changed`` when that transaction commits.
    """
    repos = BoardRepoRepository(db, org_id=org_id)
    for board_id in await repos.take_links_to(repo_id):
        changes = BoardChanges(board_id, actor_id)
        await _detach(repos, changes, repo_id)
        changes.queue(db)


async def _detach(repos: BoardRepoRepository, changes: BoardChanges, repo_id: uuid.UUID) -> None:
    cleared = await repos.detach_cards(changes.board_id, repo_id)
    await repos.unlink(changes.board_id, repo_id)
    changes.emit(
        BoardSocketEvent.REPOS_CHANGED, repo_id=str(repo_id), linked=False, cleared=cleared
    )
