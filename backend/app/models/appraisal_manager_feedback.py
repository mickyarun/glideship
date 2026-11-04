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

"""A manager's feedback for one report over one month or quarter.

Keep doing, try next and a status for each goal. The employee sees it as
soon as the manager saves it. ``manager_user_id`` is snapshotted when the
item opens and moves to a new primary manager while it is still open.
"""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.appraisal_enums import CheckInCadence, FeedbackStatus, pg_enum
from app.models.base import BaseModel


class AppraisalManagerFeedback(BaseModel):
    """One feedback item, open until the manager marks it done."""

    __tablename__ = "appraisal_manager_feedback"
    __table_args__ = (
        UniqueConstraint("profile_id", "period_start", name="uq_appraisal_feedback_period"),
        CheckConstraint("period_end > period_start", name="ck_appraisal_feedback_period"),
        CheckConstraint(
            "status <> 'done' OR done_at IS NOT NULL", name="ck_appraisal_feedback_done_at"
        ),
        Index("ix_appraisal_feedback_manager", "org_id", "manager_user_id", "status"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    cycle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appraisal_cycles.id", ondelete="CASCADE"), nullable=False
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employee_profiles.id", ondelete="CASCADE"), nullable=False
    )
    manager_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    # Feedback runs monthly or quarterly; "in the review" creates no items.
    cadence: Mapped[CheckInCadence] = mapped_column(
        pg_enum(CheckInCadence, "appraisal_checkin_cadence"), nullable=False
    )
    due_on: Mapped[date] = mapped_column(Date, nullable=False)
    keep_note: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    try_note: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    # Goal id → {"status": on_track | at_risk | off_track}. Notes on each
    # goal live in the encrypted ``goal_notes`` blob, never here.
    goal_status: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    goal_notes: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    status: Mapped[FeedbackStatus] = mapped_column(
        pg_enum(FeedbackStatus, "appraisal_feedback_status"),
        nullable=False,
        default=FeedbackStatus.OPEN,
    )
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
