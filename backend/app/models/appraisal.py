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

"""One person's appraisal in one cycle: self-score, manager review, result.

Bands run 1 (always exceeds) to 5 (does not meet). ``final_band`` is
stored when the manager submits, so later code can't move a shared
result. The scoring manager and role template are snapshotted when the
person is enrolled. Every free-text field is HR-key ciphertext.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.appraisal_enums import AppraisalStatus, DraftingMode, DraftStatus, pg_enum
from app.models.base import BaseModel

_BAND_RANGE = "BETWEEN 1 AND 5"


class Appraisal(BaseModel):
    """The review record for one enrolled person."""

    __tablename__ = "appraisals"
    __table_args__ = (
        UniqueConstraint("cycle_id", "profile_id", name="uq_appraisals_cycle_profile"),
        CheckConstraint(f"self_band {_BAND_RANGE}", name="ck_appraisals_self_band"),
        CheckConstraint(f"manager_band {_BAND_RANGE}", name="ck_appraisals_manager_band"),
        CheckConstraint(f"final_band {_BAND_RANGE}", name="ck_appraisals_final_band"),
        CheckConstraint(
            "self_submitted_at IS NULL OR self_band IS NOT NULL",
            name="ck_appraisals_self_submitted_band",
        ),
        CheckConstraint(
            "manager_submitted_at IS NULL"
            " OR (manager_band IS NOT NULL AND final_band IS NOT NULL)",
            name="ck_appraisals_manager_submitted_band",
        ),
        Index("ix_appraisals_manager", "org_id", "manager_user_id"),
        Index("ix_appraisals_profile", "profile_id"),
        Index("ix_appraisals_role_template", "role_template_id"),
        Index(
            "ix_appraisals_pending_summary",
            "summary_claimed_at",
            postgresql_where="period_summary_status = 'pending'",
        ),
        Index(
            "ix_appraisals_pending_suggestions",
            "suggest_claimed_at",
            postgresql_where="suggest_status = 'pending'",
        ),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    cycle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appraisal_cycles.id", ondelete="RESTRICT"), nullable=False
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employee_profiles.id", ondelete="CASCADE"), nullable=False
    )
    # The primary manager when the person was enrolled; they score.
    manager_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    role_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appraisal_role_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    drafting_mode: Mapped[DraftingMode] = mapped_column(
        pg_enum(DraftingMode, "appraisal_drafting_mode"), nullable=False
    )
    status: Mapped[AppraisalStatus] = mapped_column(
        pg_enum(AppraisalStatus, "appraisal_status"),
        nullable=False,
        default=AppraisalStatus.ENROLLED,
    )
    ai_period_summary: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    period_summary_status: Mapped[DraftStatus] = mapped_column(
        pg_enum(DraftStatus, "appraisal_draft_status"),
        nullable=False,
        default=DraftStatus.NONE,
    )
    summary_attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    summary_claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # An error code, never the provider's message.
    summary_error: Mapped[str | None] = mapped_column(String(60), nullable=True)
    # Suggested goals for the period: the same run states as the summary.
    suggest_status: Mapped[DraftStatus] = mapped_column(
        pg_enum(DraftStatus, "appraisal_draft_status"),
        nullable=False,
        default=DraftStatus.NONE,
    )
    suggest_attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    suggest_claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    suggest_error: Mapped[str | None] = mapped_column(String(60), nullable=True)

    self_band: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    self_reason: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    # Fact refs cited for the band, as in ``AppraisalCheckIn.fact_refs``.
    self_evidence: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    manager_band: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    manager_reason: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    manager_evidence: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    final_band: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    # Manager-only questions: never returned to the employee.
    ready_next_level: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    performance_concern: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    concern_note: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    send_back_note: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    growth_strength: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    growth_focus: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    reply: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    self_submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    manager_submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    shared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Facts that belong to the whole period (retrospectives, estimates, new
    # skills), gathered when the review opens, as in ``AppraisalCheckIn.fact_refs``.
    period_facts: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    # When each reminder stream last announced this appraisal's step: the
    # self-review opening, the manager's review (again after a send-back),
    # the shared result. Empty means the next reminder pass says so.
    self_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    result_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
