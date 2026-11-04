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

"""One person's check-in for one month (or quarter).

``fact_refs`` is the list of work Glideship recorded, saved by SQL alone,
so a check-in is complete without any AI. The AI summary is optional
prose on top, tracked by ``draft_status`` so a sweeper can claim pending
drafts from the database rather than an in-memory queue.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.appraisal_enums import CheckInStatus, DraftStatus, pg_enum
from app.models.base import BaseModel


class AppraisalCheckIn(BaseModel):
    """The facts, the optional AI draft and the employee's own lines."""

    __tablename__ = "appraisal_check_ins"
    __table_args__ = (
        UniqueConstraint("profile_id", "period_start", name="uq_appraisal_check_ins_period"),
        CheckConstraint("period_end > period_start", name="ck_appraisal_check_ins_period"),
        CheckConstraint(
            "available_days >= 0 AND available_days <= working_days",
            name="ck_appraisal_check_ins_days",
        ),
        Index("ix_appraisal_check_ins_cycle", "org_id", "cycle_id"),
        Index(
            "ix_appraisal_check_ins_open",
            "org_id",
            "period_end",
            postgresql_where="closed_at IS NULL",
        ),
        # The sweeper's claim query.
        Index(
            "ix_appraisal_check_ins_pending_draft",
            "draft_claimed_at",
            postgresql_where="draft_status = 'pending'",
        ),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employee_profiles.id", ondelete="CASCADE"), nullable=False
    )
    cycle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appraisal_cycles.id", ondelete="RESTRICT"), nullable=False
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    working_days: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    # Half days count 0.5.
    available_days: Mapped[Decimal] = mapped_column(Numeric(4, 1), nullable=False)
    # Accounts that may be this person but aren't linked yet.
    identity_warnings: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    # Each: source, id, key, title, url, done_at, board_id. Ids and titles
    # only; never decrypted HR content.
    fact_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    # When the fact list was last gathered; the scheduler refreshes it daily.
    facts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Fact id → {"heading": ..., "goal_id": ...}, set by the employee.
    fact_tags: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    ai_summary: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ai_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    draft_status: Mapped[DraftStatus] = mapped_column(
        pg_enum(DraftStatus, "appraisal_draft_status"),
        nullable=False,
        default=DraftStatus.NONE,
    )
    draft_attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    # How many redrafts were asked for: each is a paid run, and re-rolling
    # until the text flatters shouldn't be open-ended.
    redrafts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    # An error code, never the provider's message (it may echo prompt text).
    draft_error: Mapped[str | None] = mapped_column(String(60), nullable=True)
    draft_claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # The employee's lines under each heading, encrypted as one JSON blob.
    employee_note: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    status: Mapped[CheckInStatus] = mapped_column(
        pg_enum(CheckInStatus, "appraisal_check_in_status"),
        nullable=False,
        default=CheckInStatus.OPEN,
    )
    # Set when the next check-in opens (or the self-review, for the last one);
    # after that the fact list is frozen and nobody edits it.
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
