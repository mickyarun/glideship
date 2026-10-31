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

"""Data access for the repositories a board links, scoped to an organization.

A card write that names a repository holds the link row ``FOR KEY SHARE``
until it commits; unlinking takes it ``FOR UPDATE`` before clearing the
cards. Both take the link before any card row, so the two queue up
instead of deadlocking, and a card can't pick up a repository that is
being unlinked.
"""

import uuid

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_card import BoardCard
from app.models.board_repo import BoardRepo
from app.models.tracked_repository import RepoStatus, TrackedRepository


class BoardRepoRepository:
    """Linked repositories for boards in one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        self._db = db
        self._org_id = org_id

    async def list_linked(self, board_id: uuid.UUID) -> list[TrackedRepository]:
        """The repositories the board links, by name."""
        stmt = (
            select(TrackedRepository)
            .join(BoardRepo, BoardRepo.repo_id == TrackedRepository.id)
            .where(BoardRepo.org_id == self._org_id, BoardRepo.board_id == board_id)
            .order_by(func.lower(TrackedRepository.name), TrackedRepository.id)
        )
        return list((await self._db.execute(stmt)).scalars().all())

    async def options(self, board_id: uuid.UUID) -> list[tuple[TrackedRepository, bool]]:
        """The org's active repositories by name, each with whether the board links it."""
        linked = (
            select(BoardRepo.id)
            .where(BoardRepo.board_id == board_id, BoardRepo.repo_id == TrackedRepository.id)
            .exists()
        )
        stmt = (
            select(TrackedRepository, linked)
            .where(
                TrackedRepository.org_id == self._org_id,
                TrackedRepository.status == RepoStatus.ACTIVE,
            )
            .order_by(func.lower(TrackedRepository.name), TrackedRepository.id)
        )
        return [(repo, bool(flag)) for repo, flag in (await self._db.execute(stmt)).all()]

    async def active_repo(self, repo_id: uuid.UUID) -> TrackedRepository | None:
        """One of the org's active repositories, or None."""
        stmt = select(TrackedRepository).where(
            TrackedRepository.org_id == self._org_id,
            TrackedRepository.id == repo_id,
            TrackedRepository.status == RepoStatus.ACTIVE,
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def link(self, board_id: uuid.UUID, repo_id: uuid.UUID) -> bool:
        """Link the repository; False when the board already links it."""
        stmt = (
            insert(BoardRepo)
            .values(id=uuid.uuid4(), board_id=board_id, repo_id=repo_id, org_id=self._org_id)
            .on_conflict_do_nothing(constraint="uq_board_repos_board_repo")
            .returning(BoardRepo.id)
        )
        return (await self._db.execute(stmt)).first() is not None

    async def hold_link(
        self, board_id: uuid.UUID, repo_id: uuid.UUID, *, exclusive: bool = False
    ) -> bool:
        """Lock the link row (shared, or ``exclusive`` to remove it); False when absent."""
        stmt = select(BoardRepo.id).where(
            BoardRepo.org_id == self._org_id,
            BoardRepo.board_id == board_id,
            BoardRepo.repo_id == repo_id,
        )
        stmt = stmt.with_for_update() if exclusive else stmt.with_for_update(key_share=True)
        return (await self._db.execute(stmt)).first() is not None

    async def detach_cards(self, board_id: uuid.UUID, repo_id: uuid.UUID) -> list[uuid.UUID]:
        """Clear ``repo_id`` on the board's cards that name it; their ids."""
        stmt = (
            update(BoardCard)
            .where(
                BoardCard.org_id == self._org_id,
                BoardCard.board_id == board_id,
                BoardCard.repo_id == repo_id,
            )
            .values(repo_id=None, updated_at=func.now())
            .returning(BoardCard.id)
            .execution_options(synchronize_session=False)
        )
        return list((await self._db.execute(stmt)).scalars().all())

    async def unlink(self, board_id: uuid.UUID, repo_id: uuid.UUID) -> None:
        """Remove the link; the caller has detached the cards first."""
        await self._db.execute(
            delete(BoardRepo).where(
                BoardRepo.org_id == self._org_id,
                BoardRepo.board_id == board_id,
                BoardRepo.repo_id == repo_id,
            )
        )
