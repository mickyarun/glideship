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

"""Agents on board stages, and the runs they make on cards.

A stage agent pairs a stage with a skill from the org's library and says
when it runs: when a card enters the stage (``on_enter``, at most one per
stage) or from the card's Run button (``manual``). A run's output always
lands as a ``pending_review`` card document; nothing on the card changes
until someone accepts it. A card has at most one active run.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel
from app.models.board_enums import pg_enum
from app.models.board_fks import board_fk, card_fk

# Long enough for any job id the queue mints (UUID strings).
JOB_ID_LENGTH = 64


class BoardAgentTrigger(StrEnum):
    """When a stage agent runs."""

    ON_ENTER = "on_enter"
    MANUAL = "manual"


class BoardAgentRunStatus(StrEnum):
    """Where one agent run on a card stands."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


# A card has at most one run in these.
ACTIVE_RUN_STATUSES = (BoardAgentRunStatus.PENDING, BoardAgentRunStatus.RUNNING)
_ACTIVE_SQL = ", ".join(f"'{s.value}'" for s in ACTIVE_RUN_STATUSES)


class BoardStageAgent(BaseModel):
    """One agent on one stage: a library skill and when it runs."""

    __tablename__ = "board_stage_agents"
    __table_args__ = (
        board_fk("board_stage_agents"),
        ForeignKeyConstraint(
            ["stage_id", "board_id"],
            ["board_stages.id", "board_stages.board_id"],
            ondelete="CASCADE",
            name="fk_board_stage_agents_stage_board",
        ),
        UniqueConstraint("stage_id", "execution_order", name="uq_board_stage_agents_order"),
        # One active run per card means a second on_enter agent could never run.
        Index(
            "uq_board_stage_agents_one_on_enter",
            "stage_id",
            unique=True,
            postgresql_where=text(f"trigger = '{BoardAgentTrigger.ON_ENTER.value}'"),
        ),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    board_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    stage_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_skills.id", ondelete="CASCADE"), nullable=False
    )
    execution_order: Mapped[int] = mapped_column(Integer, nullable=False)
    trigger: Mapped[BoardAgentTrigger] = mapped_column(
        pg_enum(BoardAgentTrigger, "board_agent_trigger"), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<BoardStageAgent(stage_id={self.stage_id}, trigger={self.trigger.value})>"


class BoardCardAgentRun(BaseModel):
    """One run of a stage agent on a card."""

    __tablename__ = "board_card_agent_runs"
    __table_args__ = (
        card_fk("board_card_agent_runs"),
        Index("ix_board_card_agent_runs_card_created", "card_id", "created_at"),
        Index(
            "uq_board_card_agent_runs_one_active",
            "card_id",
            unique=True,
            postgresql_where=text(f"status IN ({_ACTIVE_SQL})"),
        ),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    card_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    stage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("board_stages.id", ondelete="SET NULL"), nullable=True
    )
    stage_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("board_stage_agents.id", ondelete="SET NULL"), nullable=True
    )
    skill_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_skills.id", ondelete="SET NULL"), nullable=True
    )
    trigger: Mapped[BoardAgentTrigger] = mapped_column(
        pg_enum(BoardAgentTrigger, "board_agent_trigger"), nullable=False
    )
    status: Mapped[BoardAgentRunStatus] = mapped_column(
        pg_enum(BoardAgentRunStatus, "board_agent_run_status"), nullable=False
    )
    job_id: Mapped[str | None] = mapped_column(String(JOB_ID_LENGTH), nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    result_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Who pressed Run (null for on_enter runs).
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<BoardCardAgentRun(card_id={self.card_id}, status={self.status.value})>"
