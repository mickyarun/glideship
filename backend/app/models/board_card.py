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

"""Board cards, their assignees and labels, and the keys they used to have.

A card's display key is ``f"{board.key}-{number}"``. Numbers come from
``boards.next_card_number`` and are never reused, so an old key kept in
``board_card_key_aliases`` keeps resolving after a card changes board.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Double,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel
from app.models.board_enums import pg_enum
from app.models.board_fks import board_fk, card_fk, member_fk
from app.models.bud import BUDPriority

CARD_TITLE_LENGTH = 500
CARD_KEY_LENGTH = 32
# Card numbers and document versions are int4 columns.
INT4_MAX = 2**31 - 1


class BoardCard(BaseModel):
    """One card on a board."""

    __tablename__ = "board_cards"
    __table_args__ = (
        UniqueConstraint("board_id", "number", name="uq_board_cards_board_number"),
        # Composite-FK targets for the card's child tables.
        UniqueConstraint("id", "org_id", name="uq_board_cards_id_org"),
        UniqueConstraint("id", "board_id", name="uq_board_cards_id_board"),
        board_fk("board_cards"),
        # The stage must belong to the card's own board.
        ForeignKeyConstraint(
            ["stage_id", "board_id"],
            ["board_stages.id", "board_stages.board_id"],
            name="fk_board_cards_stage_board",
        ),
        # Keyset paging of one stage's open cards on ``(position, id)``.
        Index(
            "ix_board_cards_stage_position",
            "stage_id",
            "position",
            "id",
            postgresql_where=text("archived_at IS NULL"),
        ),
        # Due reminders scan open cards by due date.
        Index(
            "ix_board_cards_org_due",
            "org_id",
            "due_at",
            postgresql_where=text("completed_at IS NULL AND archived_at IS NULL"),
        ),
        Index(
            "ix_board_cards_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    board_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    stage_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # Gap-based: inserts take the midpoint of their neighbours, and a
    # stage is rebalanced when a gap gets too small.
    position: Mapped[float] = mapped_column(Double, nullable=False)
    title: Mapped[str] = mapped_column(String(CARD_TITLE_LENGTH), nullable=False)
    description_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The BUD priority type; NULL means no priority.
    priority: Mapped[BUDPriority | None] = mapped_column(
        pg_enum(BUDPriority, "bud_priority", create_type=False), nullable=True
    )
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_done: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    # First entry into an ``in_progress`` stage.
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Entry into ``done`` or ``canceled``; cleared when the card reopens.
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<BoardCard(board_id={self.board_id}, number={self.number})>"


class BoardCardAssignee(BaseModel):
    """Join row: a member is assigned to a card. Cards can have several."""

    __tablename__ = "board_card_assignees"
    __table_args__ = (
        UniqueConstraint("card_id", "user_id", name="uq_board_card_assignees_card_user"),
        card_fk("board_card_assignees"),
        member_fk("board_card_assignees"),
        Index("ix_board_card_assignees_user_id", "user_id"),
    )

    card_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class BoardCardLabel(BaseModel):
    """Join row: a card carries one of its own board's labels.

    ``board_id`` follows the card (``ON UPDATE CASCADE``), so moving a card
    to another board fails while it still carries the old board's labels.
    """

    __tablename__ = "board_card_labels"
    __table_args__ = (
        UniqueConstraint("card_id", "label_id", name="uq_board_card_labels_card_label"),
        card_fk("board_card_labels"),
        ForeignKeyConstraint(
            ["card_id", "board_id"],
            ["board_cards.id", "board_cards.board_id"],
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_board_card_labels_card_board",
        ),
        ForeignKeyConstraint(
            ["label_id", "board_id"],
            ["board_labels.id", "board_labels.board_id"],
            ondelete="CASCADE",
            name="fk_board_card_labels_label_board",
        ),
        Index("ix_board_card_labels_label_id", "label_id"),
    )

    card_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    label_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    board_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class BoardCardKeyAlias(BaseModel):
    """A key a card used before it moved board, e.g. ``SEO-14``."""

    __tablename__ = "board_card_key_aliases"
    __table_args__ = (
        UniqueConstraint("org_id", "key", name="uq_board_card_key_aliases_org_key"),
        card_fk("board_card_key_aliases"),
        Index("ix_board_card_key_aliases_card_id", "card_id"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    key: Mapped[str] = mapped_column(String(CARD_KEY_LENGTH), nullable=False)
    card_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    def __repr__(self) -> str:
        return f"<BoardCardKeyAlias(key={self.key!r}, card_id={self.card_id})>"
