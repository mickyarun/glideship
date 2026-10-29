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

"""A card's files and links. Mirrors ``api/v1/bug_attachments.py``.

Files are served back only through the access-checked download route,
always as a download with ``nosniff`` and a sandbox CSP.
"""

import uuid

from fastapi import APIRouter, Depends, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.boards._access import edit_card, read_card
from app.core.deps import get_db
from app.core.paths import sanitize_filename
from app.schemas.boards.card_detail import AttachmentList, AttachmentRead, LinkCreate
from app.services.boards import attachment_service
from app.services.boards.access import CardAccess
from app.services.boards.attachment_rules import policy

router = APIRouter(tags=["boards"])

ATTACHMENTS = "/{key}/cards/{number}/attachments"


@router.get(ATTACHMENTS, response_model=AttachmentList)
async def list_attachments(
    target: CardAccess = Depends(read_card), db: AsyncSession = Depends(get_db)
) -> AttachmentList:
    """The card's files and links, with the upload limits."""
    return await attachment_service.list_attachments(db, target)


@router.post(ATTACHMENTS, response_model=AttachmentRead, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    file: UploadFile,
    target: CardAccess = Depends(edit_card),
    db: AsyncSession = Depends(get_db),
) -> AttachmentRead:
    """Attach one file; it's read only up to one byte past the size cap."""
    data = await file.read(policy().max_bytes + 1)
    return await attachment_service.upload_file(db, target, file.filename, data)


@router.post(
    f"{ATTACHMENTS}/links", response_model=AttachmentRead, status_code=status.HTTP_201_CREATED
)
async def add_link(
    body: LinkCreate,
    target: CardAccess = Depends(edit_card),
    db: AsyncSession = Depends(get_db),
) -> AttachmentRead:
    """Attach a link."""
    return await attachment_service.add_link(db, target, body)


@router.get(f"{ATTACHMENTS}/{{attachment_id}}")
async def download_attachment(
    attachment_id: uuid.UUID,
    target: CardAccess = Depends(read_card),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """The file's bytes, as a download."""
    data, row = await attachment_service.download(db, target, attachment_id)
    safe_name = sanitize_filename(row.filename, fallback="attachment")
    return Response(
        content=data,
        media_type=row.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )


@router.delete(f"{ATTACHMENTS}/{{attachment_id}}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attachment(
    attachment_id: uuid.UUID,
    target: CardAccess = Depends(edit_card),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove my own attachment, or any as a board admin."""
    await attachment_service.delete_attachment(db, target, attachment_id)
