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

"""One appraisal cycle: a review period and the settings it runs with.

Every setting is copied from the org's appraisal settings when the cycle
is created, so changing the org settings never moves a running cycle.
"""

import uuid
from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    LargeBinary,
    SmallInteger,
    String,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.appraisal_enums import (
    CheckInCadence,
    CycleStatus,
    FeedbackCadence,
    ReviewPeriod,
    pg_enum,
)
from app.models.base import BaseModel


class AppraisalCycle(BaseModel):
    """A review period for some or all of an org's people."""

    __tablename__ = "appraisal_cycles"
    __table_args__ = (
        CheckConstraint("period_end > period_start", name="ck_appraisal_cycles_period"),
        CheckConstraint(
            "self_due >= period_end AND manager_due >= self_due",
            name="ck_appraisal_cycles_due_dates",
        ),
        # Quarterly check-ins only fit reviews longer than a quarter.
        CheckConstraint(
            "checkin_cadence = 'monthly' OR review_period <> 'quarterly'",
            name="ck_appraisal_cycles_checkin_cadence",
        ),
        # Feedback comes more often than reviews and no more often than
        # check-ins; "in the review" stands in for quarterly feedback when
        # the reviews themselves are quarterly.
        CheckConstraint(
            "(feedback_cadence = 'in_review' AND review_period = 'quarterly')"
            " OR (feedback_cadence = 'monthly' AND checkin_cadence = 'monthly')"
            " OR (feedback_cadence = 'quarterly' AND review_period <> 'quarterly')",
            name="ck_appraisal_cycles_feedback_cadence",
        ),
        CheckConstraint(
            "enrolment_cutoff >= period_start AND enrolment_cutoff <= period_end",
            name="ck_appraisal_cycles_cutoff",
        ),
        CheckConstraint("feedback_due_days >= 0", name="ck_appraisal_cycles_feedback_due"),
        Index("ix_appraisal_cycles_org_period", "org_id", "period_start"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    self_due: Mapped[date] = mapped_column(Date, nullable=False)
    manager_due: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[CycleStatus] = mapped_column(
        pg_enum(CycleStatus, "appraisal_cycle_status"),
        nullable=False,
        default=CycleStatus.DRAFT,
    )
    review_period: Mapped[ReviewPeriod] = mapped_column(
        pg_enum(ReviewPeriod, "appraisal_review_period"), nullable=False
    )
    checkin_cadence: Mapped[CheckInCadence] = mapped_column(
        pg_enum(CheckInCadence, "appraisal_checkin_cadence"), nullable=False
    )
    feedback_cadence: Mapped[FeedbackCadence] = mapped_column(
        pg_enum(FeedbackCadence, "appraisal_feedback_cadence"), nullable=False
    )
    feedback_due_days: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    # Working days relative to each due date, e.g. [-3, 0, 2].
    reminder_offsets: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger), nullable=False)
    overdue_nudge: Mapped[bool] = mapped_column(Boolean, nullable=False)
    hr_overdue_list: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # Working days after the due date before HR's overdue list goes out.
    hr_overdue_offset: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    suggest_goals_on_open: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ai_drafting: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # People who join after this date wait for the next cycle.
    enrolment_cutoff: Mapped[date] = mapped_column(Date, nullable=False)
    # HR's note at the top of the guide, encrypted.
    intro_note: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
