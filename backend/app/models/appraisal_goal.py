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

"""A goal for one person's review period, from suggestion to result.

Suggestions and proposals are kept alongside accepted goals so the
history of where a goal came from survives; only accepted goals count
towards the limit of three and appear in the review. ``cycle_id`` is
empty for a goal set in a growth conversation before the next cycle
exists; it attaches when that cycle opens.
"""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    SmallInteger,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.appraisal_enums import (
    GoalOrigin,
    GoalResult,
    GoalStatus,
    SuggestionBasis,
    pg_enum,
)
from app.models.base import BaseModel


class AppraisalGoal(BaseModel):
    """One goal: an outcome and how the person will know they got there."""

    __tablename__ = "appraisal_goals"
    __table_args__ = (
        # Keyed on the period rather than the cycle, which may not exist yet.
        Index(
            "uq_appraisal_goals_accepted_position",
            "profile_id",
            "target_period_start",
            "position",
            unique=True,
            postgresql_where="status = 'accepted'",
        ),
        Index("ix_appraisal_goals_profile_period", "org_id", "profile_id", "target_period_start"),
        CheckConstraint("position BETWEEN 1 AND 3", name="ck_appraisal_goals_position"),
        CheckConstraint(
            "status <> 'accepted' OR position IS NOT NULL",
            name="ck_appraisal_goals_accepted_position",
        ),
        # A suggestion always says what it was drawn from.
        CheckConstraint(
            "origin <> 'ai_suggested' OR suggestion_basis IS NOT NULL",
            name="ck_appraisal_goals_suggestion_basis",
        ),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employee_profiles.id", ondelete="CASCADE"), nullable=False
    )
    cycle_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appraisal_cycles.id", ondelete="CASCADE"), nullable=True
    )
    target_period_start: Mapped[date] = mapped_column(Date, nullable=False)
    # 1–3 once accepted; empty while suggested or proposed.
    position: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    title: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    measure: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    origin: Mapped[GoalOrigin] = mapped_column(
        pg_enum(GoalOrigin, "appraisal_goal_origin"), nullable=False
    )
    proposed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    added_mid_period: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[GoalStatus] = mapped_column(
        pg_enum(GoalStatus, "appraisal_goal_status"), nullable=False
    )
    suggestion_basis: Mapped[SuggestionBasis | None] = mapped_column(
        pg_enum(SuggestionBasis, "appraisal_suggestion_basis"), nullable=True
    )
    # Fact ids, check-in ids and the trends version a suggestion cites.
    suggestion_refs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    # The suggestion as first written, encrypted, kept when someone edits it.
    original: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    dismiss_reason: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    accepted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    self_result: Mapped[GoalResult | None] = mapped_column(
        pg_enum(GoalResult, "appraisal_goal_result"), nullable=True
    )
    self_reason: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    self_evidence: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    final_result: Mapped[GoalResult | None] = mapped_column(
        pg_enum(GoalResult, "appraisal_goal_result"), nullable=True
    )
    manager_reason: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
