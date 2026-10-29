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

"""Data access for the :class:`app.models.bug_comment.BugComment` thread."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bug_comment import BugComment
from app.repositories.thread import CommentThreadRepository


class BugCommentRepository(CommentThreadRepository[BugComment]):
    """Repository for bug-comment queries, scoped to an organization."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        super().__init__(BugComment, BugComment.bug_id, db, org_id=org_id)

    async def list_for_bug(
        self, bug_id: uuid.UUID, *, include_deleted: bool = True
    ) -> list[BugComment]:
        """All comments on a bug, oldest first, tombstones included by default."""
        return await self.list_comments(bug_id, include_deleted=include_deleted)

    async def count_active_by_bug(self, bug_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        """Bulk-count non-deleted comments per bug id.

        Used by the board card badge ("3 comments"). Bugs with no
        comments are absent from the returned dict.
        """
        return await self.count_active_by_parent(bug_ids)
