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

"""Tracked repositories a board links, the way ``team_repos`` links them to teams.

Both keys pair with ``org_id``, so a board can only link its own org's
repositories. A card's ``repo_id`` references this row, so a card can only
name a repository its board links.
"""

import uuid

from sqlalchemy import ForeignKeyConstraint, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel
from app.models.board_fks import board_fk


class BoardRepo(BaseModel):
    """Join row: a board links a tracked repository."""

    __tablename__ = "board_repos"
    __table_args__ = (
        # Also the composite-FK target for ``board_cards(board_id, repo_id)``.
        UniqueConstraint("board_id", "repo_id", name="uq_board_repos_board_repo"),
        board_fk("board_repos"),
        ForeignKeyConstraint(
            ["repo_id", "org_id"],
            ["tracked_repositories.id", "tracked_repositories.org_id"],
            ondelete="CASCADE",
            name="fk_board_repos_repo_org",
        ),
        Index("ix_board_repos_repo_id", "repo_id"),
    )

    board_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    repo_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    def __repr__(self) -> str:
        return f"<BoardRepo(board_id={self.board_id}, repo_id={self.repo_id})>"
