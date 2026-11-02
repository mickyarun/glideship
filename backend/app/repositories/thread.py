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

"""Generic data access for rows that hang off one parent, oldest first.

Comments and attachments on bugs and board cards are each their own table,
keyed by a different parent column. These repositories take that column
once and share the queries.
"""

import uuid
from datetime import UTC, datetime
from typing import Protocol, TypeVar

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.models.base import BaseModel as ORMBase
from app.models.thread_columns import CommentColumns
from app.repositories.base import BaseRepository

C = TypeVar("C", bound=ORMBase)
CM = TypeVar("CM", bound=CommentColumns)


class HasAuthor(Protocol):
    """A thread row with an author; imported rows may have none."""

    @property
    def author_id(self) -> uuid.UUID | None:
        """The user who wrote the row."""
        ...


def is_comment_author(comment: HasAuthor, user_id: uuid.UUID) -> bool:
    """True when ``user_id`` wrote ``comment``; authorless rows have no author to match."""
    return comment.author_id is not None and comment.author_id == user_id


class ThreadRepository(BaseRepository[C]):
    """Tenant-scoped queries over a model's rows for one parent.

    Args:
        model: The thread's ORM model.
        parent_col: The model's foreign key to its parent, e.g. ``BugComment.bug_id``.
        db: An active async database session.
        org_id: The tenant every query is scoped to.
    """

    def __init__(
        self,
        model: type[C],
        parent_col: InstrumentedAttribute[uuid.UUID],
        db: AsyncSession,
        *,
        org_id: uuid.UUID,
    ) -> None:
        super().__init__(model, db, org_id=org_id)
        self._parent_col = parent_col

    async def get_in_parent(self, parent_id: uuid.UUID, row_id: uuid.UUID) -> C | None:
        """One row, or None when it's missing or belongs to another parent."""
        stmt = self._scoped(
            select(self._model).where(self._model.id == row_id, self._parent_col == parent_id)
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_parent(
        self, parent_id: uuid.UUID, *conditions: ColumnElement[bool]
    ) -> list[C]:
        """A parent's rows, oldest first, narrowed by any extra ``conditions``."""
        stmt = self._scoped(
            select(self._model)
            .where(self._parent_col == parent_id, *conditions)
            .order_by(self._model.created_at.asc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def count_for_parent(
        self, parent_id: uuid.UUID, *conditions: ColumnElement[bool]
    ) -> int:
        """How many rows one parent has, narrowed by any extra ``conditions``."""
        stmt = self._scoped(
            select(func.count())
            .select_from(self._model)
            .where(self._parent_col == parent_id, *conditions)
        )
        result = await self._db.execute(stmt)
        return result.scalar_one()

    async def count_by_parent(
        self, parent_ids: list[uuid.UUID], *conditions: ColumnElement[bool]
    ) -> dict[uuid.UUID, int]:
        """Bulk-count rows per parent; parents with none are absent."""
        if not parent_ids:
            return {}
        stmt = self._scoped(
            select(self._parent_col, func.count(self._model.id))
            .where(self._parent_col.in_(parent_ids), *conditions)
            .group_by(self._parent_col)
        )
        result = await self._db.execute(stmt)
        return {row[0]: row[1] for row in result.all()}


class CommentThreadRepository(ThreadRepository[CM]):
    """A comment thread: tombstone deletes and edit stamps on top of the queries."""

    async def list_comments(
        self, parent_id: uuid.UUID, *, include_deleted: bool = True
    ) -> list[CM]:
        """All comments on a parent, oldest first (thread order).

        Soft-deleted comments are included by default so the UI can
        render a "[deleted]" tombstone in-place; callers that want a
        clean export should pass ``include_deleted=False``.
        """
        if include_deleted:
            return await self.list_for_parent(parent_id)
        return await self.list_for_parent(parent_id, self._model.deleted_at.is_(None))

    async def count_active_by_parent(self, parent_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        """Bulk-count non-deleted comments per parent id."""
        return await self.count_by_parent(parent_ids, self._model.deleted_at.is_(None))

    async def update_body(self, comment: CM, body: str) -> CM:
        """Edit a comment's body and stamp ``edited_at``."""
        comment.body = body
        comment.edited_at = datetime.now(UTC)
        await self._db.flush()
        await self._db.refresh(comment)
        return comment

    async def soft_delete(self, comment: CM) -> CM:
        """Tombstone a comment without removing the row.

        Audit trail and any future notification follow-ups need the
        original author + timestamp; the UI renders ``[deleted]`` when
        ``deleted_at`` is set.
        """
        comment.deleted_at = datetime.now(UTC)
        await self._db.flush()
        await self._db.refresh(comment)
        return comment
