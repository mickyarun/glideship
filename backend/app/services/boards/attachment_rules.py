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

"""Upload and text limits, and the lookups both attachment modules share."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.board import BOARD_NAME_LENGTH, LABEL_NAME_LENGTH, STAGE_NAME_LENGTH
from app.models.board_card import CARD_TITLE_LENGTH
from app.models.board_card_detail import BoardCardAttachment
from app.repositories.board_card_thread import BoardCardAttachmentRepository
from app.schemas.boards.card_detail import AttachmentLimits, AttachmentRead
from app.schemas.boards.limits import BoardLimits
from app.services.boards import constants as const
from app.services.boards.access import CardAccess
from app.services.boards.errors import BoardItemNotFoundError
from app.services.boards.live import BoardChanges, BoardSocketEvent
from app.services.upload_policy import UploadPolicy, card_attachment_policy


def policy() -> UploadPolicy:
    """What a card accepts, from ``BoardsConfig``."""
    return card_attachment_policy(
        max_file_mb=settings.boards.attachment_max_file_mb,
        max_files=settings.boards.attachment_max_files,
    )


def limits() -> AttachmentLimits:
    """The card policy as the picker reads it."""
    rules = policy()
    return AttachmentLimits(
        max_file_mb=rules.max_mb,
        max_files=rules.max_files or 0,
        accepted_extensions=sorted(rules.extensions or {}),
    )


ATTACHMENT_NOT_FOUND = "Attachment not found."


async def get_attachment(
    db: AsyncSession, target: CardAccess, attachment_id: uuid.UUID
) -> BoardCardAttachment:
    repo = BoardCardAttachmentRepository(db, org_id=target.access.org_id)
    """One of the card's attachments; another card's id is not found."""
    row = await repo.get_in_parent(target.card.id, attachment_id)
    if row is None:
        raise BoardItemNotFoundError(ATTACHMENT_NOT_FOUND)
    return row


async def announce(
    db: AsyncSession, target: CardAccess, row: BoardCardAttachment
) -> AttachmentRead:
    """Commit and tell the board the card's attachments changed."""
    read = AttachmentRead.model_validate(row)
    changes = BoardChanges.of(target.access)
    changes.emit(BoardSocketEvent.CARD_ACTIVITY, card_id=str(target.card.id))
    await changes.commit(db)
    return read


def board_limits() -> BoardLimits:
    """Every limit the boards UI needs, from the constants, columns and settings."""
    return BoardLimits(
        board_name_max=BOARD_NAME_LENGTH,
        board_description_max=const.BOARD_DESCRIPTION_MAX_CHARS,
        stage_name_max=STAGE_NAME_LENGTH,
        max_stages=settings.boards.max_stages_per_board,
        wip_limit_max=const.WIP_LIMIT_MAX,
        label_name_max=LABEL_NAME_LENGTH,
        card_title_max=CARD_TITLE_LENGTH,
        card_description_max=const.CARD_DESCRIPTION_MAX_CHARS,
        doc_max=const.CARD_DOC_MAX_CHARS,
        comment_max=const.COMMENT_MAX_CHARS,
        checklist_text_max=const.CHECKLIST_TEXT_MAX_CHARS,
        checklist_max_items=const.CHECKLIST_MAX_ITEMS,
        links_max_per_card=const.LINKS_MAX_PER_CARD,
        id_list_max_items=const.ID_LIST_MAX_ITEMS,
        search_max=const.SEARCH_MAX_CHARS,
        filters_max_bytes=settings.boards.filters_max_bytes,
        stage_page_size=settings.boards.stage_page_size,
        attachments=limits(),
    )
