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

"""A card's documents, edited by hand, with their versions and the drafts agents write."""

import uuid

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.boards._access import edit_card, review_draft, view_card
from app.config import settings
from app.core.deps import get_db
from app.models.board_card import INT4_MAX
from app.models.board_enums import BoardCardDocKind
from app.schemas.boards.agent import DraftAccept
from app.schemas.boards.doc import DocList, DocRead, DocRestore, DocVersionPage, DocWrite
from app.services.boards import doc_service
from app.services.boards.access import CardAccess
from app.services.boards.agents import drafts

router = APIRouter(tags=["boards"])

DOCS = "/{key}/cards/{number}/docs"


@router.get(DOCS, response_model=DocList)
async def list_docs(
    target: CardAccess = Depends(view_card), db: AsyncSession = Depends(get_db)
) -> DocList:
    """The current version of each document."""
    return await doc_service.list_docs(db, target)


@router.get(f"{DOCS}/{{kind}}/versions", response_model=DocVersionPage)
async def list_versions(
    kind: BoardCardDocKind,
    before: int | None = Query(default=None, ge=1, le=INT4_MAX),
    limit: int | None = Query(default=None, ge=1, le=settings.boards.versions_page_size),
    target: CardAccess = Depends(view_card),
    db: AsyncSession = Depends(get_db),
) -> DocVersionPage:
    """A page of one document's versions, newest first, without their text."""
    return await doc_service.list_versions(db, target, kind, before=before, limit=limit)


@router.get(f"{DOCS}/{{kind}}/versions/{{version}}", response_model=DocRead)
async def get_version(
    kind: BoardCardDocKind,
    version: int = Path(..., ge=1, le=INT4_MAX),
    target: CardAccess = Depends(view_card),
    db: AsyncSession = Depends(get_db),
) -> DocRead:
    """One version with its text."""
    return await doc_service.get_version(db, target, kind, version)


@router.put(f"{DOCS}/{{kind}}", response_model=DocRead)
async def write_doc(
    kind: BoardCardDocKind,
    body: DocWrite,
    target: CardAccess = Depends(edit_card),
    db: AsyncSession = Depends(get_db),
) -> DocRead:
    """Save a new current version; 409 if the current one isn't ``base_version``."""
    return await doc_service.write_doc(
        db, target, kind, body.body_md, base_version=body.base_version
    )


@router.post(f"{DOCS}/{{kind}}/restore/{{version}}", response_model=DocRead)
async def restore_version(
    kind: BoardCardDocKind,
    body: DocRestore,
    version: int = Path(..., ge=1, le=INT4_MAX),
    target: CardAccess = Depends(edit_card),
    db: AsyncSession = Depends(get_db),
) -> DocRead:
    """Make an old version's text current again; 409 if the current one isn't ``base_version``."""
    return await doc_service.restore_version(
        db, target, kind, version, base_version=body.base_version
    )


@router.post(f"{DOCS}/{{kind}}/drafts/{{version_id}}/accept", response_model=DocRead)
async def accept_draft(
    kind: BoardCardDocKind,
    version_id: uuid.UUID,
    body: DraftAccept,
    target: CardAccess = Depends(review_draft),
    db: AsyncSession = Depends(get_db),
) -> DocRead:
    """Make an agent's draft (or ``body_md``, the reviewer's edit of it) the current version.

    404 when the draft was already reviewed or replaced; 409 if the current
    version isn't ``base_version``.
    """
    return await drafts.accept_draft(db, target, kind, version_id, body)


@router.post(f"{DOCS}/{{kind}}/drafts/{{version_id}}/reject", response_model=DocRead)
async def reject_draft(
    kind: BoardCardDocKind,
    version_id: uuid.UUID,
    target: CardAccess = Depends(review_draft),
    db: AsyncSession = Depends(get_db),
) -> DocRead:
    """Reject an agent's draft; the card keeps its current version."""
    return await drafts.reject_draft(db, target, kind, version_id)
