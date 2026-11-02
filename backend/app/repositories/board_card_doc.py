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

"""Data access for card document versions, scoped to an organization."""

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from app.models.board_card_doc import BoardCardDoc
from app.models.board_enums import BoardCardDocKind, BoardCardDocState
from app.repositories.base import BaseRepository


class BoardCardDocRepository(BaseRepository[BoardCardDoc]):
    """Tenant-scoped repository for card documents."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        super().__init__(BoardCardDoc, db, org_id=org_id)

    async def current_docs(self, card_id: uuid.UUID) -> list[BoardCardDoc]:
        """The current version of each kind of document on the card."""
        stmt = self._scoped(
            select(BoardCardDoc)
            .where(
                BoardCardDoc.card_id == card_id,
                BoardCardDoc.state == BoardCardDocState.CURRENT,
            )
            .order_by(BoardCardDoc.kind)
        )
        return list((await self._db.execute(stmt)).scalars().all())

    async def current(self, card_id: uuid.UUID, kind: BoardCardDocKind) -> BoardCardDoc | None:
        """The current version of one kind, if there is one."""
        stmt = self._scoped(
            select(BoardCardDoc).where(
                BoardCardDoc.card_id == card_id,
                BoardCardDoc.kind == kind,
                BoardCardDoc.state == BoardCardDocState.CURRENT,
            )
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def versions(
        self, card_id: uuid.UUID, kind: BoardCardDocKind, *, before: int | None, limit: int
    ) -> list[BoardCardDoc]:
        """Up to ``limit`` versions older than ``before``, newest first, bodies not loaded."""
        stmt = self._scoped(
            select(BoardCardDoc)
            .options(defer(BoardCardDoc.body_md, raiseload=True))
            .where(BoardCardDoc.card_id == card_id, BoardCardDoc.kind == kind)
        )
        if before is not None:
            stmt = stmt.where(BoardCardDoc.version < before)
        stmt = stmt.order_by(BoardCardDoc.version.desc()).limit(limit)
        return list((await self._db.execute(stmt)).scalars().all())

    async def get_version(
        self, card_id: uuid.UUID, kind: BoardCardDocKind, version: int
    ) -> BoardCardDoc | None:
        """One version of one kind, if it exists."""
        stmt = self._scoped(
            select(BoardCardDoc).where(
                BoardCardDoc.card_id == card_id,
                BoardCardDoc.kind == kind,
                BoardCardDoc.version == version,
            )
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def next_version(self, card_id: uuid.UUID, kind: BoardCardDocKind) -> int:
        """The number the next version of this kind gets."""
        stmt = self._scoped(
            select(func.coalesce(func.max(BoardCardDoc.version), 0)).where(
                BoardCardDoc.card_id == card_id, BoardCardDoc.kind == kind
            )
        )
        return int((await self._db.execute(stmt)).scalar_one()) + 1

    async def supersede_current(self, card_id: uuid.UUID, kind: BoardCardDocKind) -> None:
        """Mark the current version of this kind superseded."""
        stmt = (
            update(BoardCardDoc)
            .where(
                BoardCardDoc.org_id == self._org_id,
                BoardCardDoc.card_id == card_id,
                BoardCardDoc.kind == kind,
                BoardCardDoc.state == BoardCardDocState.CURRENT,
            )
            .values(state=BoardCardDocState.SUPERSEDED)
            .execution_options(synchronize_session="fetch")
        )
        await self._db.execute(stmt)

    async def drafts(self, card_id: uuid.UUID) -> list[BoardCardDoc]:
        """The card's ``pending_review`` versions, newest first."""
        stmt = self._scoped(
            select(BoardCardDoc)
            .where(
                BoardCardDoc.card_id == card_id,
                BoardCardDoc.state == BoardCardDocState.PENDING_REVIEW,
            )
            .order_by(BoardCardDoc.created_at.desc(), BoardCardDoc.version.desc())
        )
        return list((await self._db.execute(stmt)).scalars().all())

    async def get_draft(
        self, card_id: uuid.UUID, kind: BoardCardDocKind, doc_id: uuid.UUID
    ) -> BoardCardDoc | None:
        """One ``pending_review`` version of one kind, if it is still waiting."""
        stmt = self._scoped(
            select(BoardCardDoc).where(
                BoardCardDoc.id == doc_id,
                BoardCardDoc.card_id == card_id,
                BoardCardDoc.kind == kind,
                BoardCardDoc.state == BoardCardDocState.PENDING_REVIEW,
            )
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def supersede_drafts(self, card_id: uuid.UUID, kind: BoardCardDocKind) -> None:
        """Retire the kind's waiting drafts; a newer draft replaces them."""
        stmt = (
            update(BoardCardDoc)
            .where(
                BoardCardDoc.org_id == self._org_id,
                BoardCardDoc.card_id == card_id,
                BoardCardDoc.kind == kind,
                BoardCardDoc.state == BoardCardDocState.PENDING_REVIEW,
            )
            .values(state=BoardCardDocState.SUPERSEDED)
            .execution_options(synchronize_session="fetch")
        )
        await self._db.execute(stmt)

    async def written_by_run(self, run_id: uuid.UUID) -> BoardCardDoc | None:
        """The newest version a run wrote, if it wrote one."""
        stmt = self._scoped(
            select(BoardCardDoc)
            .where(BoardCardDoc.agent_run_id == run_id)
            .order_by(BoardCardDoc.version.desc())
            .limit(1)
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()
