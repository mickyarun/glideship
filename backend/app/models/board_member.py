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

"""Who has a role on a board, and each person's board preferences.

Every row reaches its user through ``(user_id, org_id)`` →
``org_to_user``, so offboarding a member cascades their board rows away
exactly as it does their ``team_members`` rows.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKeyConstraint,
    Index,
    UniqueConstraint,
    false,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel
from app.models.board_enums import BoardMemberRole, pg_enum
from app.models.board_fks import board_fk, member_fk


class BoardMember(BaseModel):
    """An individual's role on a board."""

    __tablename__ = "board_members"
    __table_args__ = (
        UniqueConstraint("board_id", "user_id", name="uq_board_members_board_user"),
        board_fk("board_members"),
        member_fk("board_members"),
        Index("ix_board_members_user_id", "user_id"),
    )

    board_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    role: Mapped[BoardMemberRole] = mapped_column(
        pg_enum(BoardMemberRole, "board_member_role"), nullable=False
    )

    def __repr__(self) -> str:
        return f"<BoardMember(board_id={self.board_id}, user_id={self.user_id})>"


class BoardTeam(BaseModel):
    """A team's role on a board; every member of the team holds it."""

    __tablename__ = "board_teams"
    __table_args__ = (
        UniqueConstraint("board_id", "team_id", name="uq_board_teams_board_team"),
        board_fk("board_teams"),
        ForeignKeyConstraint(
            ["team_id", "org_id"],
            ["teams.id", "teams.org_id"],
            ondelete="CASCADE",
            name="fk_board_teams_team_org",
        ),
        Index("ix_board_teams_team_id", "team_id"),
    )

    board_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    team_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    role: Mapped[BoardMemberRole] = mapped_column(
        pg_enum(BoardMemberRole, "board_member_role"), nullable=False
    )

    def __repr__(self) -> str:
        return f"<BoardTeam(board_id={self.board_id}, team_id={self.team_id})>"


class BoardUserPrefs(BaseModel):
    """One person's star, last visit and saved filters for one board."""

    __tablename__ = "board_user_prefs"
    __table_args__ = (
        UniqueConstraint("board_id", "user_id", name="uq_board_user_prefs_board_user"),
        board_fk("board_user_prefs"),
        member_fk("board_user_prefs"),
        Index("ix_board_user_prefs_user_id", "user_id"),
    )

    board_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    starred: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    last_opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    filters: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )

    def __repr__(self) -> str:
        return f"<BoardUserPrefs(board_id={self.board_id}, user_id={self.user_id})>"
