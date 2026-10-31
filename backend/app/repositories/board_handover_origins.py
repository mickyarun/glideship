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

"""Which card each of a page of BUDs came from, for the Delivery board's origin chips."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board import Board
from app.models.board_card import BoardCard
from app.models.board_handover import BoardCardHandover
from app.models.bud import BUDDocument
from app.repositories.board_access import BoardAccessRepository, PermissionChecker
from app.repositories.board_handover import live_handover


@dataclass(frozen=True)
class VisibleOrigin:
    """A BUD's live origin card, on a board the caller holds a role on."""

    bud_id: uuid.UUID
    board_key: str
    card_number: int


class BoardHandoverOriginRepository:
    """Live origin cards of many BUDs at once, limited to boards the caller can open."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        self._db = db
        self._org_id = org_id

    async def visible_live_origins(
        self, bud_ids: list[uuid.UUID], user_id: uuid.UUID, perms: PermissionChecker
    ) -> list[VisibleOrigin]:
        """The live origin (see :func:`live_handover`) of each BUD whose card's board the caller
        holds a role on, in one statement. A BUD has at most one live origin.
        """
        if not bud_ids:
            return []
        roles = BoardAccessRepository(self._db, org_id=self._org_id).role_subquery(
            user_id, perms, name="origin_roles"
        )
        stmt = (
            select(BoardCardHandover.bud_id, Board.key, BoardCard.number)
            .join(
                BUDDocument,
                (BUDDocument.id == BoardCardHandover.bud_id)
                & (BUDDocument.org_id == BoardCardHandover.org_id),
            )
            .join(
                BoardCard,
                (BoardCard.id == BoardCardHandover.card_id)
                & (BoardCard.org_id == BoardCardHandover.org_id),
            )
            .join(Board, (Board.id == BoardCard.board_id) & (Board.org_id == BoardCard.org_id))
            .join(roles, roles.c.board_id == Board.id)
            .where(
                BoardCardHandover.org_id == self._org_id,
                BoardCardHandover.bud_id.in_(bud_ids),
                live_handover(),
            )
        )
        rows = (await self._db.execute(stmt)).all()
        return [VisibleOrigin(row[0], row[1], row[2]) for row in rows]
