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

"""Card comments and attachments on the shared thread repositories."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, literal, select, tuple_
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_card_detail import BoardCardAttachment, BoardCardComment
from app.models.board_enums import BoardAttachmentKind
from app.repositories.thread import CommentThreadRepository, ThreadRepository


class BoardCardCommentRepository(CommentThreadRepository[BoardCardComment]):
    """Tenant-scoped comment thread for one card at a time."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        super().__init__(BoardCardComment, BoardCardComment.card_id, db, org_id=org_id)

    async def page(
        self, card_id: uuid.UUID, *, after: tuple[datetime, uuid.UUID] | None, limit: int
    ) -> list[BoardCardComment]:
        """Up to ``limit`` comments, oldest first, after the ``(created_at, id)`` given."""
        stmt = self._scoped(select(BoardCardComment).where(BoardCardComment.card_id == card_id))
        if after is not None:
            at, comment_id = after
            stmt = stmt.where(
                tuple_(BoardCardComment.created_at, BoardCardComment.id)
                > tuple_(
                    literal(at, DateTime(timezone=True)), literal(comment_id, UUID(as_uuid=True))
                )
            )
        stmt = stmt.order_by(BoardCardComment.created_at, BoardCardComment.id).limit(limit)
        return list((await self._db.execute(stmt)).scalars().all())


class BoardCardAttachmentRepository(ThreadRepository[BoardCardAttachment]):
    """Tenant-scoped files and links on cards."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        super().__init__(BoardCardAttachment, BoardCardAttachment.card_id, db, org_id=org_id)

    async def count_kind(self, card_id: uuid.UUID, kind: BoardAttachmentKind) -> int:
        """The card's files, or its links; each has its own cap."""
        return await self.count_for_parent(card_id, BoardCardAttachment.kind == kind)
