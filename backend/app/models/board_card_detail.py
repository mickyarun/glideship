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

"""What hangs off a card: checklist items, comments, attachments and events."""

import uuid
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Double,
    ForeignKey,
    Index,
    String,
    Text,
    false,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel
from app.models.board_enums import (
    BoardAttachmentKind,
    BoardCardEventType,
    BoardStageCategory,
    pg_enum,
)
from app.models.board_fks import board_fk, card_fk
from app.models.external_import import ImportSourceKind
from app.models.thread_columns import CommentColumns, OptionalAttachmentColumns

CHECKLIST_GROUP_LENGTH = 255
EXTERNAL_LABEL_LENGTH = 255
EXTERNAL_REF_LENGTH = 128
ATTACHMENT_URL_LENGTH = 2000


class BoardCardChecklistItem(BaseModel):
    """One checklist line; ``group_name`` keeps imported checklists apart."""

    __tablename__ = "board_card_checklist_items"
    __table_args__ = (
        card_fk("board_card_checklist_items"),
        Index("ix_board_card_checklist_items_card_position", "card_id", "position"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    card_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    group_name: Mapped[str | None] = mapped_column(String(CHECKLIST_GROUP_LENGTH), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    done: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    position: Mapped[float] = mapped_column(Double, nullable=False)


class BoardCardComment(CommentColumns):
    """A comment on a card.

    Imported comments carry ``import_source``; one by an unmapped person has
    an ``author_label`` and no author.
    """

    __tablename__ = "board_card_comments"
    __table_args__ = (
        card_fk("board_card_comments"),
        Index("ix_board_card_comments_card_created", "card_id", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    card_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Shown when there's no author, e.g. "Priya (Trello)".
    author_label: Mapped[str | None] = mapped_column(String(EXTERNAL_LABEL_LENGTH), nullable=True)
    # Set on every imported comment, mapped author or not, so it reads as imported.
    import_source: Mapped[ImportSourceKind | None] = mapped_column(
        pg_enum(ImportSourceKind, "import_source_kind"), nullable=True
    )


class BoardCardAttachment(OptionalAttachmentColumns):
    """A file stored in ``FileStorage``, or a link, attached to a card."""

    __tablename__ = "board_card_attachments"
    __table_args__ = (
        card_fk("board_card_attachments"),
        CheckConstraint(
            f"(kind = '{BoardAttachmentKind.FILE.value}' AND storage_path IS NOT NULL"
            " AND mime_type IS NOT NULL AND size_bytes IS NOT NULL)"
            f" OR (kind = '{BoardAttachmentKind.LINK.value}' AND url IS NOT NULL)",
            name="ck_board_card_attachments_kind_fields",
        ),
        Index("ix_board_card_attachments_card_created", "card_id", "created_at"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    card_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    kind: Mapped[BoardAttachmentKind] = mapped_column(
        pg_enum(BoardAttachmentKind, "board_attachment_kind"), nullable=False
    )
    url: Mapped[str | None] = mapped_column(String(ATTACHMENT_URL_LENGTH), nullable=True)


class BoardCardEvent(BaseModel):
    """One entry in a card's history.

    ``board_id`` and both categories are frozen at write time, so per-board
    cycle time and throughput stay right after a card moves board or a
    stage is re-categorised.
    """

    __tablename__ = "board_card_events"
    __table_args__ = (
        card_fk("board_card_events"),
        # Boards are archived, never deleted, so history is never lost.
        board_fk("board_card_events", ondelete="RESTRICT"),
        Index(
            "ix_board_card_events_org_board_category_created",
            "org_id",
            "board_id",
            "to_category",
            "created_at",
        ),
        Index("ix_board_card_events_card_created", "card_id", "created_at"),
        # An event from outside (a pull request, a commit) is recorded once per card.
        Index(
            "uq_board_card_events_card_external_ref",
            "card_id",
            "external_ref",
            unique=True,
            postgresql_where=text("external_ref IS NOT NULL"),
        ),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    card_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    board_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    type: Mapped[BoardCardEventType] = mapped_column(
        pg_enum(BoardCardEventType, "board_card_event_type"), nullable=False
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Who did it when there's no user, e.g. an imported action.
    actor_label: Mapped[str | None] = mapped_column(String(EXTERNAL_LABEL_LENGTH), nullable=True)
    # Single-column keys so a deleted stage nulls just its id (pg14 has no
    # column-list SET NULL); the service keeps both stages on ``board_id``.
    from_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("board_stages.id", ondelete="SET NULL"), nullable=True
    )
    to_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("board_stages.id", ondelete="SET NULL"), nullable=True
    )
    from_category: Mapped[BoardStageCategory | None] = mapped_column(
        pg_enum(BoardStageCategory, "board_stage_category"), nullable=True
    )
    to_category: Mapped[BoardStageCategory | None] = mapped_column(
        pg_enum(BoardStageCategory, "board_stage_category"), nullable=True
    )
    detail: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    # What an event from outside is about, e.g. ``<repo id>:commit:<sha>``; null otherwise.
    external_ref: Mapped[str | None] = mapped_column(String(EXTERNAL_REF_LENGTH), nullable=True)
