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

"""A card's comment thread: anyone on the board comments, only authors edit.

Deletes are tombstones: the row keeps its place, with an empty body.
Every lookup goes through ``get_in_parent``, so a comment id from another
card is simply not found.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.board_card_detail import BoardCardComment
from app.models.board_enums import BoardCardEventType
from app.repositories.board_card_thread import BoardCardCommentRepository
from app.repositories.thread import is_comment_author
from app.repositories.user import PersonCard, UserRepository
from app.schemas.boards.card_detail import CommentPage, CommentRead
from app.services.boards.access import CardAccess
from app.services.boards.card_checks import check_open
from app.services.boards.cursor import decode_time_cursor, encode_cursor
from app.services.boards.errors import (
    BoardActionForbiddenError,
    BoardConflictError,
    BoardItemNotFoundError,
)
from app.services.boards.events import record_event
from app.services.boards.live import BoardChanges, BoardSocketEvent


async def list_comments(
    db: AsyncSession, target: CardAccess, *, cursor: str | None, limit: int | None
) -> CommentPage:
    """A page of the card's thread, oldest first, tombstones in place."""
    size = limit or settings.boards.comments_page_size
    repo = BoardCardCommentRepository(db, org_id=target.access.org_id)
    after = decode_time_cursor(cursor) if cursor else None
    rows = await repo.page(target.card.id, after=after, limit=size + 1)
    page = rows[:size]
    last = page[-1] if page and len(rows) > size else None
    return CommentPage(
        items=await _read(db, target, page),
        next_cursor=None
        if last is None
        else encode_cursor(last.created_at.isoformat(), str(last.id)),
    )


async def add_comment(db: AsyncSession, target: CardAccess, body: str) -> CommentRead:
    """Post a comment as the caller."""
    access, card = target.access, target.card
    check_open(card)
    comment = await BoardCardCommentRepository(db, org_id=access.org_id).create(
        BoardCardComment(
            org_id=access.org_id, card_id=card.id, author_id=access.user_id, body=body
        )
    )
    await record_event(
        db,
        card,
        BoardCardEventType.COMMENTED,
        actor_id=access.user_id,
        detail={"comment_id": str(comment.id)},
    )
    return await _announce(db, target, comment)


async def edit_comment(
    db: AsyncSession, target: CardAccess, comment_id: uuid.UUID, body: str
) -> CommentRead:
    """Change the caller's own comment."""
    check_open(target.card)
    repo = BoardCardCommentRepository(db, org_id=target.access.org_id)
    comment = await _own(repo, target, comment_id)
    if comment.deleted_at is not None:
        raise BoardConflictError("A deleted comment can't be edited.")
    return await _announce(db, target, await repo.update_body(comment, body))


async def delete_comment(
    db: AsyncSession, target: CardAccess, comment_id: uuid.UUID
) -> CommentRead:
    """Tombstone the caller's own comment; deleting it again changes nothing."""
    check_open(target.card)
    repo = BoardCardCommentRepository(db, org_id=target.access.org_id)
    comment = await _own(repo, target, comment_id)
    if comment.deleted_at is not None:
        (read,) = await _read(db, target, [comment])
        return read
    return await _announce(db, target, await repo.soft_delete(comment))


async def _own(
    repo: BoardCardCommentRepository, target: CardAccess, comment_id: uuid.UUID
) -> BoardCardComment:
    comment = await repo.get_in_parent(target.card.id, comment_id)
    if comment is None:
        raise BoardItemNotFoundError("Comment not found.")
    if not is_comment_author(comment, target.access.user_id):
        raise BoardActionForbiddenError("Only the comment's author can change it.")
    return comment


async def _announce(
    db: AsyncSession, target: CardAccess, comment: BoardCardComment
) -> CommentRead:
    (read,) = await _read(db, target, [comment])
    changes = BoardChanges.of(target.access)
    changes.emit(BoardSocketEvent.CARD_ACTIVITY, card_id=str(target.card.id))
    await changes.commit(db)
    return read


async def _read(
    db: AsyncSession, target: CardAccess, comments: list[BoardCardComment]
) -> list[CommentRead]:
    people = await UserRepository(db, org_id=target.access.org_id).get_people_by_ids(
        {c.author_id for c in comments if c.author_id is not None}
    )
    return [_comment(c, people.get(c.author_id) if c.author_id else None) for c in comments]


def _comment(comment: BoardCardComment, author: PersonCard | None) -> CommentRead:
    return CommentRead(
        id=comment.id,
        author_id=comment.author_id,
        author_label=comment.author_label,
        author_name=author.name if author else None,
        author_avatar_url=author.avatar_url if author else None,
        body="" if comment.deleted_at is not None else comment.body,
        import_source=comment.import_source,
        edited_at=comment.edited_at,
        deleted_at=comment.deleted_at,
        created_at=comment.created_at,
    )
