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

"""Files and links on a card.

Files go through :class:`FileStorage` under the card policy from
:func:`card_attachment_policy`; the type comes from the extension, never
the browser. Links don't count toward the per-card file cap. Only the
uploader or a board admin can remove an attachment.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.paths import sanitize_filename
from app.models.board_card_detail import BoardCardAttachment
from app.models.board_enums import BoardAttachmentKind, BoardMemberRole
from app.models.thread_columns import ATTACHMENT_FILENAME_LENGTH
from app.repositories.board_card import BoardCardRepository
from app.repositories.board_card_thread import BoardCardAttachmentRepository
from app.schemas.boards.card_detail import (
    AttachmentList,
    AttachmentRead,
    LinkCreate,
)
from app.services.boards.access import CardAccess
from app.services.boards.attachment_rules import limits, policy
from app.services.boards.card_checks import check_open
from app.services.boards.errors import (
    BoardActionForbiddenError,
    BoardConflictError,
    BoardItemNotFoundError,
    BoardRuleError,
    BoardTooLargeError,
)
from app.services.boards.live import BoardChanges, BoardSocketEvent
from app.services.boards.reads import card_key
from app.services.file_storage import FileStorageError, get_file_storage
from app.services.upload_policy import UploadPolicyError

ATTACHMENT_NOT_FOUND = "Attachment not found."


async def list_attachments(db: AsyncSession, target: CardAccess) -> AttachmentList:
    """The card's files and links, oldest first, with the limits."""
    repo = BoardCardAttachmentRepository(db, org_id=target.access.org_id)
    rows = await repo.list_for_parent(target.card.id)
    return AttachmentList(items=[AttachmentRead.model_validate(r) for r in rows], limits=limits())


async def upload_file(
    db: AsyncSession, target: CardAccess, filename: str | None, data: bytes
) -> AttachmentRead:
    """Store ``data`` and attach it to the card.

    ``data`` was read up to one byte past the cap, so an oversized file is
    caught here without reading all of it.
    """
    access, card = target.access, target.card
    # Held so two uploads can't both pass the file-count check.
    await BoardCardRepository(db, org_id=access.org_id).lock(card)
    check_open(card)
    rules = policy()
    repo = BoardCardAttachmentRepository(db, org_id=access.org_id)
    try:
        rules.check_count(await repo.count_files(card.id))
    except UploadPolicyError as exc:
        raise BoardConflictError(str(exc)) from exc
    safe_name = sanitize_filename(filename, fallback="attachment")
    try:
        mime = rules.resolve_mime(safe_name)
    except UploadPolicyError as exc:
        raise BoardRuleError(str(exc)) from exc
    try:
        rules.check_size(len(data))
    except UploadPolicyError as exc:
        raise BoardTooLargeError(str(exc)) from exc
    if not data:
        raise BoardRuleError(f"{safe_name} is empty.")
    # {org}/board-attachments/SEO-14/{random}-{name}: readable in the bucket,
    # and two files of the same name on one card don't collide.
    folder = card_key(access.board, card.number)
    path = f"board-attachments/{folder}/{uuid.uuid4().hex[:12]}-{safe_name}"
    try:
        stored = await get_file_storage().upload(
            org_id=str(access.org_id),
            relative_path=path,
            data=data,
            content_type=mime,
            policy=rules,
        )
    except FileStorageError as exc:
        raise BoardRuleError(str(exc)) from exc
    row = BoardCardAttachment(
        org_id=access.org_id,
        card_id=card.id,
        kind=BoardAttachmentKind.FILE,
        filename=safe_name,
        mime_type=mime,
        size_bytes=len(data),
        storage_path=stored,
        uploaded_by=access.user_id,
    )
    return await _announce(db, target, await repo.create(row))


async def add_link(db: AsyncSession, target: CardAccess, body: LinkCreate) -> AttachmentRead:
    """Attach a link to the card."""
    access, card = target.access, target.card
    check_open(card)
    url = str(body.url)
    row = BoardCardAttachment(
        org_id=access.org_id,
        card_id=card.id,
        kind=BoardAttachmentKind.LINK,
        filename=body.title or url[:ATTACHMENT_FILENAME_LENGTH],
        url=url,
        uploaded_by=access.user_id,
    )
    repo = BoardCardAttachmentRepository(db, org_id=access.org_id)
    return await _announce(db, target, await repo.create(row))


async def download(
    db: AsyncSession, target: CardAccess, attachment_id: uuid.UUID
) -> tuple[bytes, BoardCardAttachment]:
    """A stored file's bytes and its row."""
    row = await _get(db, target, attachment_id)
    if row.kind is not BoardAttachmentKind.FILE or row.storage_path is None:
        raise BoardItemNotFoundError("That attachment is a link, not a file.")
    try:
        data, _ = await get_file_storage().download(row.storage_path)
    except FileStorageError as exc:
        raise BoardItemNotFoundError(str(exc)) from exc
    return data, row


async def delete_attachment(
    db: AsyncSession, target: CardAccess, attachment_id: uuid.UUID
) -> None:
    """Remove an attachment: the uploader's own, or any for a board admin.

    The stored file goes first, so a storage failure leaves the row for a retry.
    """
    access = target.access
    row = await _get(db, target, attachment_id)
    if row.uploaded_by != access.user_id and not access.role.at_least(BoardMemberRole.ADMIN):
        raise BoardActionForbiddenError(
            "Only the person who added this, or a board admin, can remove it."
        )
    if row.storage_path is not None:
        try:
            await get_file_storage().delete(row.storage_path)
        except FileStorageError as exc:
            raise BoardConflictError("Could not remove the stored file. Try again.") from exc
    await BoardCardAttachmentRepository(db, org_id=access.org_id).delete(row)
    changes = BoardChanges(access.board.id)
    changes.emit(BoardSocketEvent.CARD_ACTIVITY, card_id=str(target.card.id))
    await changes.commit(db)


async def _get(
    db: AsyncSession, target: CardAccess, attachment_id: uuid.UUID
) -> BoardCardAttachment:
    repo = BoardCardAttachmentRepository(db, org_id=target.access.org_id)
    row = await repo.get_in_parent(target.card.id, attachment_id)
    if row is None:
        raise BoardItemNotFoundError(ATTACHMENT_NOT_FOUND)
    return row


async def _announce(
    db: AsyncSession, target: CardAccess, row: BoardCardAttachment
) -> AttachmentRead:
    read = AttachmentRead.model_validate(row)
    changes = BoardChanges(target.access.board.id)
    changes.emit(BoardSocketEvent.CARD_ACTIVITY, card_id=str(target.card.id))
    await changes.commit(db)
    return read
