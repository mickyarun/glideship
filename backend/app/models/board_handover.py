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

"""A card handed over to dev: the one record of where a BUD came from.

A card can hold several handovers, one per BUD. A BUD has at most one
active origin card. Every confirm's ``idempotency_key`` (from the client)
is kept in ``board_card_handover_keys``, so a retry or a double click of
any confirm, even one before a send-back and a second handover, returns
that handover instead of making another BUD.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    false,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel
from app.models.board_enums import BoardHandoverStatus, pg_enum
from app.models.board_fks import card_fk
from app.models.bud import BUDStatus


class BoardCardHandover(BaseModel):
    """One BUD a card was handed over to (or linked to)."""

    __tablename__ = "board_card_handovers"
    __table_args__ = (
        card_fk("board_card_handovers"),
        UniqueConstraint("card_id", "bud_id", name="uq_board_card_handovers_card_bud"),
        UniqueConstraint(
            "card_id", "idempotency_key", name="uq_board_card_handovers_card_idempotency"
        ),
        # A BUD has one live origin card.
        Index(
            "uq_board_card_handovers_one_active_bud",
            "bud_id",
            unique=True,
            postgresql_where=text(f"status = '{BoardHandoverStatus.ACTIVE.value}'"),
        ),
        Index("ix_board_card_handovers_card_at", "card_id", "handed_over_at"),
        Index("ix_board_card_handovers_bud", "bud_id"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    card_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    bud_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bud_documents.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[BoardHandoverStatus] = mapped_column(
        pg_enum(BoardHandoverStatus, "board_handover_status"),
        nullable=False,
        default=BoardHandoverStatus.ACTIVE,
        server_default=BoardHandoverStatus.ACTIVE.value,
    )
    # Linked to a BUD that already existed, rather than creating one.
    linked_existing: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    # Where a created BUD landed; null for a link.
    target_status: Mapped[BUDStatus | None] = mapped_column(
        pg_enum(BUDStatus, "bud_status", create_type=False), nullable=True
    )
    handed_over_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    handed_over_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    returned_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    return_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The key of the confirm that made the row live now; every key is in
    # ``board_card_handover_keys``, which replays read.
    idempotency_key: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # Set when the target stage's agent failed to start after the commit;
    # cleared once a retry starts it.
    stage_start_failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<BoardCardHandover(card_id={self.card_id}, bud_id={self.bud_id})>"


class BoardCardHandoverKey(BaseModel):
    """One confirm's idempotency key on a card, and the handover it made or reused."""

    __tablename__ = "board_card_handover_keys"
    __table_args__ = (
        card_fk("board_card_handover_keys"),
        UniqueConstraint(
            "card_id", "idempotency_key", name="uq_board_card_handover_keys_card_key"
        ),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    card_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    handover_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("board_card_handovers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
