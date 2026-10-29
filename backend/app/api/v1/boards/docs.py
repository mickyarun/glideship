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

"""A card's documents, edited by hand, with their versions."""

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.boards._access import edit_card, read_card
from app.core.deps import get_db
from app.models.board_card import INT4_MAX
from app.models.board_enums import BoardCardDocKind
from app.schemas.boards.doc import DocList, DocRead, DocWrite
from app.services.boards import doc_service
from app.services.boards.access import CardAccess

router = APIRouter(tags=["boards"])

DOCS = "/{key}/cards/{number}/docs"


@router.get(DOCS, response_model=DocList)
async def list_docs(
    target: CardAccess = Depends(read_card), db: AsyncSession = Depends(get_db)
) -> DocList:
    """The current version of each document."""
    return await doc_service.list_docs(db, target)


@router.get(f"{DOCS}/{{kind}}/versions", response_model=list[DocRead])
async def list_versions(
    kind: BoardCardDocKind,
    target: CardAccess = Depends(read_card),
    db: AsyncSession = Depends(get_db),
) -> list[DocRead]:
    """Every version of one document, newest first."""
    return await doc_service.list_versions(db, target, kind)


@router.put(f"{DOCS}/{{kind}}", response_model=DocRead)
async def write_doc(
    kind: BoardCardDocKind,
    body: DocWrite,
    target: CardAccess = Depends(edit_card),
    db: AsyncSession = Depends(get_db),
) -> DocRead:
    """Save a new current version of one document."""
    return await doc_service.write_doc(db, target, kind, body.body_md)


@router.post(f"{DOCS}/{{kind}}/restore/{{version}}", response_model=DocRead)
async def restore_version(
    kind: BoardCardDocKind,
    version: int = Path(..., ge=1, le=INT4_MAX),
    target: CardAccess = Depends(edit_card),
    db: AsyncSession = Depends(get_db),
) -> DocRead:
    """Make an old version's text current again."""
    return await doc_service.restore_version(db, target, kind, version)
