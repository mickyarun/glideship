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

"""Shared columns for comment threads and file attachments.

Bugs and board cards each keep their own tables, so foreign-key cascades
and composite org keys stay per parent, but the columns are declared once
here. Each table adds its own parent id, ``org_id`` and author column.
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel

ATTACHMENT_FILENAME_LENGTH = 500
ATTACHMENT_MIME_TYPE_LENGTH = 100
ATTACHMENT_STORAGE_PATH_LENGTH = 1000


class CommentColumns(BaseModel):
    """Body plus edit and tombstone stamps for one comment.

    Soft-deleted via ``deleted_at`` so the UI can render a tombstone in
    place; ``edited_at`` is stamped on every edit.
    """

    __abstract__ = True

    body: Mapped[str] = mapped_column(Text, nullable=False)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class _AttachmentMeta(BaseModel):
    """Display name and uploader, present on every attachment row."""

    __abstract__ = True

    filename: Mapped[str] = mapped_column(String(ATTACHMENT_FILENAME_LENGTH), nullable=False)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class AttachmentColumns(_AttachmentMeta):
    """A file held in :class:`app.services.file_storage.FileStorage`.

    ``mime_type`` is the canonical type derived from the filename at
    upload time, never the browser-supplied one.
    """

    __abstract__ = True

    mime_type: Mapped[str] = mapped_column(String(ATTACHMENT_MIME_TYPE_LENGTH), nullable=False)
    # BigInteger rather than Integer: the per-org cap is configurable and
    # a future raise past 2 GB should not need a column migration.
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_path: Mapped[str] = mapped_column(
        String(ATTACHMENT_STORAGE_PATH_LENGTH), nullable=False
    )


class OptionalAttachmentColumns(_AttachmentMeta):
    """The same file columns for tables that also hold links.

    A link row carries a URL and no stored file, so the file columns are
    nullable; the owning table checks which set a row must fill.
    """

    __abstract__ = True

    mime_type: Mapped[str | None] = mapped_column(
        String(ATTACHMENT_MIME_TYPE_LENGTH), nullable=True
    )
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    storage_path: Mapped[str | None] = mapped_column(
        String(ATTACHMENT_STORAGE_PATH_LENGTH), nullable=True
    )
