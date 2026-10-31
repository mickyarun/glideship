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


"""Cards a pull request or commit names, and their ``repo_activity`` events, for one org.

Only cards on active boards that link the (active) repository count, found
by their live key or an old one. Each activity is recorded once per card:
the event's ``external_ref`` is unique per card.
"""

import uuid
from typing import Any

from sqlalchemy import select, text, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.board import Board
from app.models.board_card import BoardCard, BoardCardKeyAlias
from app.models.board_card_detail import BoardCardEvent
from app.models.board_enums import BoardCardEventType, BoardStatus
from app.models.board_repo import BoardRepo
from app.models.tracked_repository import RepoStatus, TrackedRepository


class BoardRepoActivityRepository:
    """Repo activity on cards in one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        self._db = db
        self._org_id = org_id

    async def cards_named(self, repo_id: uuid.UUID, keys: set[tuple[str, int]]) -> list[BoardCard]:
        """Cards whose live or old key is one of ``keys``, on active boards linking the repo."""
        if not keys:
            return []
        pairs = sorted(keys)
        linked = (
            select(BoardRepo.board_id)
            .join(TrackedRepository, TrackedRepository.id == BoardRepo.repo_id)
            .where(
                BoardRepo.org_id == self._org_id,
                BoardRepo.repo_id == repo_id,
                TrackedRepository.status == RepoStatus.ACTIVE,
            )
        )
        live = (
            select(BoardCard.id)
            .join(Board, Board.id == BoardCard.board_id)
            .where(Board.org_id == self._org_id, tuple_(Board.key, BoardCard.number).in_(pairs))
        )
        old_board = aliased(Board)
        old = (
            select(BoardCardKeyAlias.card_id)
            .join(old_board, old_board.id == BoardCardKeyAlias.board_id)
            .where(
                BoardCardKeyAlias.org_id == self._org_id,
                old_board.org_id == self._org_id,
                tuple_(old_board.key, BoardCardKeyAlias.number).in_(pairs),
            )
        )
        stmt = (
            select(BoardCard)
            .join(Board, Board.id == BoardCard.board_id)
            .where(
                BoardCard.org_id == self._org_id,
                Board.status == BoardStatus.ACTIVE,
                BoardCard.board_id.in_(linked),
                BoardCard.id.in_(live.union(old)),
            )
            .order_by(BoardCard.id)
        )
        return list((await self._db.execute(stmt)).scalars().all())

    async def add_once(
        self,
        card: BoardCard,
        *,
        external_ref: str,
        actor_label: str | None,
        detail: dict[str, Any],
    ) -> bool:
        """Record the activity on the card; False when it was already recorded."""
        stmt = (
            insert(BoardCardEvent)
            .values(
                id=uuid.uuid4(),
                org_id=self._org_id,
                card_id=card.id,
                board_id=card.board_id,
                type=BoardCardEventType.REPO_ACTIVITY,
                actor_label=actor_label,
                detail=detail,
                external_ref=external_ref,
            )
            .on_conflict_do_nothing(
                index_elements=["card_id", "external_ref"],
                index_where=text("external_ref IS NOT NULL"),
            )
            .returning(BoardCardEvent.id)
        )
        return (await self._db.execute(stmt)).first() is not None
