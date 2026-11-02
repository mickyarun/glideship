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

"""Links on a card, downloading a stored file, and removing an attachment."""

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_card_detail import BoardCardAttachment
from app.models.board_enums import BoardAttachmentKind
from app.repositories.board_card import BoardCardRepository
from app.repositories.board_card_thread import BoardCardAttachmentRepository
from app.schemas.boards.card_detail import AttachmentRead, LinkCreate
from app.services.attachment_upload import fit_filename
from app.services.boards.access import CardAccess
from app.services.boards.attachment_rules import ATTACHMENT_NOT_FOUND, announce, get_attachment
from app.services.boards.card_checks import check_open
from app.services.boards.constants import LINKS_MAX_PER_CARD, BoardAction
from app.services.boards.errors import (
    BoardActionForbiddenError,
    BoardConflictError,
    BoardItemNotFoundError,
    BoardStorageError,
)
from app.services.boards.live import BoardChanges, BoardSocketEvent
from app.services.file_storage import FileStorageError, get_file_storage

logger = structlog.get_logger(__name__)


async def add_link(db: AsyncSession, target: CardAccess, body: LinkCreate) -> AttachmentRead:
    """Attach a link to the card."""
    access, card = target.access, target.card
    await BoardCardRepository(db, org_id=access.org_id).lock(card)
    check_open(card)
    repo = BoardCardAttachmentRepository(db, org_id=access.org_id)
    if await repo.count_kind(card.id, BoardAttachmentKind.LINK) >= LINKS_MAX_PER_CARD:
        raise BoardConflictError(f"A card can hold at most {LINKS_MAX_PER_CARD} links.")
    url = str(body.url)
    row = BoardCardAttachment(
        org_id=access.org_id,
        card_id=card.id,
        kind=BoardAttachmentKind.LINK,
        filename=body.title or fit_filename(url),
        url=url,
        uploaded_by=access.user_id,
    )
    return await announce(db, target, await repo.create(row))


async def download(
    db: AsyncSession, target: CardAccess, attachment_id: uuid.UUID
) -> tuple[bytes, BoardCardAttachment]:
    """A stored file's bytes and its row."""
    row = await get_attachment(db, target, attachment_id)
    if row.kind is not BoardAttachmentKind.FILE or row.storage_path is None:
        raise BoardItemNotFoundError("That attachment is a link, not a file.")
    try:
        data, _ = await get_file_storage().download(row.storage_path)
    except FileStorageError as exc:
        logger.error("card_attachment_download_failed", attachment_id=str(row.id), error=str(exc))
        raise BoardItemNotFoundError(ATTACHMENT_NOT_FOUND) from exc
    return data, row


async def delete_attachment(
    db: AsyncSession, target: CardAccess, attachment_id: uuid.UUID
) -> None:
    """Remove an attachment: your own, or anyone's with ``REMOVE_ANY_ATTACHMENT``.

    The stored file goes first, so a storage failure leaves the row for a retry.
    """
    access = target.access
    check_open(target.card)
    row = await get_attachment(db, target, attachment_id)
    if row.uploaded_by != access.user_id and not access.may(BoardAction.REMOVE_ANY_ATTACHMENT):
        raise BoardActionForbiddenError(
            "Only the person who added this, or a board admin, can remove it."
        )
    if row.storage_path is not None:
        try:
            await get_file_storage().delete(row.storage_path)
        except FileStorageError as exc:
            logger.error(
                "card_attachment_delete_failed", attachment_id=str(row.id), error=str(exc)
            )
            raise BoardStorageError("Could not remove the stored file. Try again.") from exc
    await BoardCardAttachmentRepository(db, org_id=access.org_id).delete(row)
    changes = BoardChanges.of(access)
    changes.emit(BoardSocketEvent.CARD_ACTIVITY, card_id=str(target.card.id))
    await changes.commit(db)
