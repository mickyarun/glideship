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

"""Versioned documents on a card: the PRD, the design brief and notes.

AI output lands here as a ``pending_review`` version, so an agent never
overwrites the card's description. At handover the current PRD becomes the
BUD's requirements and the design brief goes into its design context.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel
from app.models.board_enums import BoardCardDocKind, BoardCardDocState, pg_enum
from app.models.board_keys import card_fk
from app.models.bud_version import BUDEditSource


class BoardCardDoc(BaseModel):
    """One version of one kind of document on a card."""

    __tablename__ = "board_card_docs"
    __table_args__ = (
        UniqueConstraint("card_id", "kind", "version", name="uq_board_card_docs_version"),
        card_fk("board_card_docs"),
        # At most one current version per kind.
        Index(
            "uq_board_card_docs_one_current",
            "card_id",
            "kind",
            unique=True,
            postgresql_where=text("state = 'current'"),
        ),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    card_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    kind: Mapped[BoardCardDocKind] = mapped_column(
        pg_enum(BoardCardDocKind, "board_card_doc_kind"), nullable=False
    )
    state: Mapped[BoardCardDocState] = mapped_column(
        pg_enum(BoardCardDocState, "board_card_doc_state"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    body_md: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[BUDEditSource] = mapped_column(
        pg_enum(BUDEditSource, "bud_edit_source", create_type=False), nullable=False
    )
    # The stage-agent run that wrote this version, when one did.
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<BoardCardDoc(card_id={self.card_id}, kind={self.kind.value}, v={self.version})>"
