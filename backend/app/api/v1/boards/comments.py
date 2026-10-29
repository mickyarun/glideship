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

"""A card's comment thread: anyone on the board comments; authors edit and delete.

Mirrors ``api/v1/bug_comments.py``: tombstone deletes, author-only changes.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.boards._access import comment_card, read_card
from app.core.deps import get_db
from app.schemas.boards.card_detail import CommentBody, CommentRead
from app.services.boards import comment_service
from app.services.boards.access import CardAccess

router = APIRouter(tags=["boards"])

COMMENTS = "/{key}/cards/{number}/comments"


@router.get(COMMENTS, response_model=list[CommentRead])
async def list_comments(
    target: CardAccess = Depends(read_card), db: AsyncSession = Depends(get_db)
) -> list[CommentRead]:
    """The thread, oldest first, with deleted comments as tombstones."""
    return await comment_service.list_comments(db, target)


@router.post(COMMENTS, response_model=CommentRead, status_code=status.HTTP_201_CREATED)
async def add_comment(
    body: CommentBody,
    target: CardAccess = Depends(comment_card),
    db: AsyncSession = Depends(get_db),
) -> CommentRead:
    """Post a comment."""
    return await comment_service.add_comment(db, target, body.body)


@router.patch(f"{COMMENTS}/{{comment_id}}", response_model=CommentRead)
async def edit_comment(
    comment_id: uuid.UUID,
    body: CommentBody,
    target: CardAccess = Depends(comment_card),
    db: AsyncSession = Depends(get_db),
) -> CommentRead:
    """Edit my own comment."""
    return await comment_service.edit_comment(db, target, comment_id, body.body)


@router.delete(f"{COMMENTS}/{{comment_id}}", response_model=CommentRead)
async def delete_comment(
    comment_id: uuid.UUID,
    target: CardAccess = Depends(comment_card),
    db: AsyncSession = Depends(get_db),
) -> CommentRead:
    """Delete my own comment, leaving a tombstone."""
    return await comment_service.delete_comment(db, target, comment_id)
