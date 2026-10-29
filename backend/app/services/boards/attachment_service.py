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

"""Uploading files to a card.

Uploads share ``services/attachment_upload`` with bugs. The count and type
are checked under a short card lock before the body is read; the bytes
are stored with no lock held; then the card is locked again, the count
re-checked and the row written. If that last step fails, the stored file
is removed. Links, downloads and removal live in ``attachment_links``.
"""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_card_detail import BoardCardAttachment
from app.models.board_enums import BoardAttachmentKind
from app.repositories.board_card import BoardCardRepository
from app.repositories.board_card_thread import BoardCardAttachmentRepository
from app.schemas.boards.card_detail import AttachmentList, AttachmentRead
from app.services.attachment_upload import (
    CheckedName,
    UploadProblem,
    UploadRejectedError,
    precheck,
    store,
)
from app.services.boards.access import CardAccess
from app.services.boards.attachment_rules import announce, limits, policy
from app.services.boards.card_checks import check_open
from app.services.boards.errors import (
    BoardConflictError,
    BoardError,
    BoardRuleError,
    BoardStorageError,
    BoardTooLargeError,
)
from app.services.boards.reads import card_key
from app.services.file_storage import FileStorageError, get_file_storage

logger = structlog.get_logger(__name__)

_REJECTED: dict[UploadProblem, type[BoardError]] = {
    UploadProblem.COUNT: BoardConflictError,
    UploadProblem.TYPE: BoardRuleError,
    UploadProblem.SIZE: BoardTooLargeError,
    UploadProblem.EMPTY: BoardRuleError,
    UploadProblem.STORAGE: BoardStorageError,
}


def _board_error(exc: UploadRejectedError) -> BoardError:
    return _REJECTED[exc.problem](str(exc))


async def list_attachments(db: AsyncSession, target: CardAccess) -> AttachmentList:
    """The card's files and links, oldest first, with the limits."""
    repo = BoardCardAttachmentRepository(db, org_id=target.access.org_id)
    rows = await repo.list_for_parent(target.card.id)
    return AttachmentList(items=[AttachmentRead.model_validate(r) for r in rows], limits=limits())


async def _locked_file_check(
    db: AsyncSession, target: CardAccess, filename: str | None
) -> CheckedName:
    await BoardCardRepository(db, org_id=target.access.org_id).lock(target.card)
    check_open(target.card)
    repo = BoardCardAttachmentRepository(db, org_id=target.access.org_id)
    existing = await repo.count_kind(target.card.id, BoardAttachmentKind.FILE)
    try:
        return precheck(policy(), filename, existing)
    except UploadRejectedError as exc:
        raise _board_error(exc) from exc


async def prepare_upload(
    db: AsyncSession, target: CardAccess, filename: str | None
) -> CheckedName:
    """Check the count and type before the body is read, then let the lock go."""
    name = await _locked_file_check(db, target, filename)
    await db.commit()
    return name


async def upload_file(
    db: AsyncSession, target: CardAccess, name: CheckedName, data: bytes
) -> AttachmentRead:
    """Store ``data`` (read one byte past the cap) and attach it to the card."""
    access, card = target.access, target.card
    try:
        stored = await store(
            policy(),
            get_file_storage(),
            org_id=access.org_id,
            folder=f"board-attachments/{card_key(access.board, card.number)}",
            name=name,
            data=data,
        )
    except UploadRejectedError as exc:
        raise _board_error(exc) from exc
    try:
        await _locked_file_check(db, target, stored.filename)
        row = await BoardCardAttachmentRepository(db, org_id=access.org_id).create(
            BoardCardAttachment(
                org_id=access.org_id,
                card_id=card.id,
                kind=BoardAttachmentKind.FILE,
                filename=stored.filename,
                mime_type=stored.mime_type,
                size_bytes=stored.size_bytes,
                storage_path=stored.storage_path,
                uploaded_by=access.user_id,
            )
        )
        return await announce(db, target, row)
    except BaseException:
        await _discard(stored.storage_path)
        raise


async def _discard(storage_path: str) -> None:
    try:
        await get_file_storage().delete(storage_path)
    except FileStorageError as exc:
        logger.error("card_attachment_orphaned", storage_path=storage_path, error=str(exc))
