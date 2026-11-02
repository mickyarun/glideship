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

"""A card's assignees and labels, replaced as whole sets."""

import uuid
from collections.abc import Iterable

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_card import BoardCard, BoardCardAssignee, BoardCardLabel


class BoardCardLinkRepository:
    """Assignee and label rows for cards in one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        self._db = db
        self._org_id = org_id

    async def assignee_ids(self, card_id: uuid.UUID) -> set[uuid.UUID]:
        """Who the card is assigned to."""
        stmt = select(BoardCardAssignee.user_id).where(
            BoardCardAssignee.org_id == self._org_id, BoardCardAssignee.card_id == card_id
        )
        return set((await self._db.execute(stmt)).scalars().all())

    async def label_ids(self, card_id: uuid.UUID) -> set[uuid.UUID]:
        """Which labels the card carries."""
        stmt = select(BoardCardLabel.label_id).where(
            BoardCardLabel.org_id == self._org_id, BoardCardLabel.card_id == card_id
        )
        return set((await self._db.execute(stmt)).scalars().all())

    def create_links(
        self, card: BoardCard, *, label_ids: Iterable[uuid.UUID], user_ids: Iterable[uuid.UUID]
    ) -> None:
        """Add labels and assignees to a card created in this transaction.

        A new card has none yet, so nothing is read first; the rows go out
        with the next flush.
        """
        self._db.add_all(
            BoardCardLabel(
                card_id=card.id, label_id=label, board_id=card.board_id, org_id=self._org_id
            )
            for label in set(label_ids)
        )
        self._db.add_all(
            BoardCardAssignee(card_id=card.id, user_id=u, org_id=self._org_id)
            for u in set(user_ids)
        )

    async def set_assignees(
        self, card: BoardCard, user_ids: Iterable[uuid.UUID]
    ) -> tuple[set[uuid.UUID], set[uuid.UUID]]:
        """Make ``user_ids`` the card's assignees; returns (added, removed)."""
        wanted, current = set(user_ids), await self.assignee_ids(card.id)
        added, removed = wanted - current, current - wanted
        if removed:
            await self._db.execute(
                delete(BoardCardAssignee).where(
                    BoardCardAssignee.org_id == self._org_id,
                    BoardCardAssignee.card_id == card.id,
                    BoardCardAssignee.user_id.in_(removed),
                )
            )
        self._db.add_all(
            BoardCardAssignee(card_id=card.id, user_id=u, org_id=self._org_id) for u in added
        )
        await self._db.flush()
        return added, removed

    async def set_labels(
        self, card: BoardCard, label_ids: Iterable[uuid.UUID]
    ) -> tuple[set[uuid.UUID], set[uuid.UUID]]:
        """Make ``label_ids`` the card's labels; returns (added, removed)."""
        wanted, current = set(label_ids), await self.label_ids(card.id)
        added, removed = wanted - current, current - wanted
        if removed:
            await self._db.execute(
                delete(BoardCardLabel).where(
                    BoardCardLabel.org_id == self._org_id,
                    BoardCardLabel.card_id == card.id,
                    BoardCardLabel.label_id.in_(removed),
                )
            )
        self._db.add_all(
            BoardCardLabel(
                card_id=card.id, label_id=label, board_id=card.board_id, org_id=self._org_id
            )
            for label in added
        )
        await self._db.flush()
        return added, removed
