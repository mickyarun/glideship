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

"""Boards, their user-named stages and their labels.

Child rows carry ``org_id`` and reach their board through the composite
``(board_id, org_id)`` key, the same tenant wiring ``models/team.py`` uses,
so a row can never point at another org's board.
"""

import uuid

from sqlalchemy import (
    Boolean,
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
from app.models.board_enums import (
    BoardLabelColor,
    BoardStageCategory,
    BoardStatus,
    BoardVisibility,
    pg_enum,
)
from app.models.board_fks import board_fk
from app.models.bud import BUDStatus
from app.services.boards.constants import BOARD_KEY_MAX_LENGTH

BOARD_NAME_LENGTH = 150
STAGE_NAME_LENGTH = 60
LABEL_NAME_LENGTH = 100


class Board(BaseModel):
    """A team board with its own stages, members and card numbering."""

    __tablename__ = "boards"
    __table_args__ = (
        UniqueConstraint("org_id", "key", name="uq_boards_org_key"),
        UniqueConstraint("org_id", "name", name="uq_boards_org_name"),
        # Composite-FK target for the child tables' ``(board_id, org_id)``.
        UniqueConstraint("id", "org_id", name="uq_boards_id_org"),
        # The handover and return stages must be stages of this board.
        # ``use_alter``: ``board_stages`` references ``boards`` too.
        ForeignKeyConstraint(
            ["handover_stage_id", "id"],
            ["board_stages.id", "board_stages.board_id"],
            use_alter=True,
            name="fk_boards_handover_stage",
        ),
        ForeignKeyConstraint(
            ["return_stage_id", "id"],
            ["board_stages.id", "board_stages.board_id"],
            use_alter=True,
            name="fk_boards_return_stage",
        ),
        Index("ix_boards_org_status", "org_id", "status"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(BOARD_NAME_LENGTH), nullable=False)
    key: Mapped[str] = mapped_column(String(BOARD_KEY_MAX_LENGTH), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[BoardStatus] = mapped_column(
        pg_enum(BoardStatus, "board_status"),
        nullable=False,
        default=BoardStatus.ACTIVE,
        server_default=BoardStatus.ACTIVE.value,
    )
    visibility: Mapped[BoardVisibility] = mapped_column(
        pg_enum(BoardVisibility, "board_visibility"),
        nullable=False,
        default=BoardVisibility.ORG,
        server_default=BoardVisibility.ORG.value,
    )
    handover_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    handover_stage_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    return_stage_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # The existing ``bud_status`` type; the service limits it to the
    # statuses a handed-over card may land in.
    handover_target_status: Mapped[BUDStatus] = mapped_column(
        pg_enum(BUDStatus, "bud_status", create_type=False),
        nullable=False,
        default=BUDStatus.BUD,
        server_default=BUDStatus.BUD.value,
    )
    ai_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    # Only ever goes up, so a card number is never handed out twice.
    next_card_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<Board(key={self.key!r}, status={self.status.value})>"


class BoardStage(BaseModel):
    """A user-named column on a board, with a fixed category."""

    __tablename__ = "board_stages"
    __table_args__ = (
        UniqueConstraint("board_id", "name", name="uq_board_stages_board_name"),
        # Composite-FK target for cards and the board's handover stages.
        UniqueConstraint("id", "board_id", name="uq_board_stages_id_board"),
        board_fk("board_stages"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    board_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(STAGE_NAME_LENGTH), nullable=False)
    category: Mapped[BoardStageCategory] = mapped_column(
        pg_enum(BoardStageCategory, "board_stage_category"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    # Soft: the board shows the limit, it never blocks a move.
    wip_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    def __repr__(self) -> str:
        return f"<BoardStage(name={self.name!r}, category={self.category.value})>"


class BoardLabel(BaseModel):
    """A coloured label cards on one board can carry."""

    __tablename__ = "board_labels"
    __table_args__ = (
        UniqueConstraint("board_id", "name", name="uq_board_labels_board_name"),
        # Composite-FK target, so a card only carries its own board's labels.
        UniqueConstraint("id", "board_id", name="uq_board_labels_id_board"),
        board_fk("board_labels"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    board_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(LABEL_NAME_LENGTH), nullable=False)
    color: Mapped[BoardLabelColor] = mapped_column(
        pg_enum(BoardLabelColor, "board_label_color"), nullable=False
    )

    def __repr__(self) -> str:
        return f"<BoardLabel(name={self.name!r}, color={self.color.value})>"
