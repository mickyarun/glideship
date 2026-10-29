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

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_card_detail import BoardCardAttachment, BoardCardComment
from app.models.board_enums import BoardAttachmentKind
from app.repositories.thread import CommentThreadRepository, ThreadRepository


class BoardCardCommentRepository(CommentThreadRepository[BoardCardComment]):
    """Tenant-scoped comment thread for one card at a time."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        super().__init__(BoardCardComment, BoardCardComment.card_id, db, org_id=org_id)


class BoardCardAttachmentRepository(ThreadRepository[BoardCardAttachment]):
    """Tenant-scoped files and links on cards."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        super().__init__(BoardCardAttachment, BoardCardAttachment.card_id, db, org_id=org_id)

    async def count_files(self, card_id: uuid.UUID) -> int:
        """Stored files on the card; links don't count toward the cap."""
        return await self.count_for_parent(
            card_id, BoardCardAttachment.kind == BoardAttachmentKind.FILE
        )
