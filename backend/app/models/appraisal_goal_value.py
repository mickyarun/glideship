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

"""This month's value for a goal's measure, with where it came from.

For roles whose numbers live outside Glideship (a helpdesk report, a
search console export), shown as "reported by" the employee.
"""

import uuid

from sqlalchemy import ForeignKey, Index, LargeBinary, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class AppraisalGoalValue(BaseModel):
    """One goal's value on one check-in."""

    __tablename__ = "appraisal_goal_values"
    __table_args__ = (
        UniqueConstraint("goal_id", "check_in_id", name="uq_appraisal_goal_values_check_in"),
        Index("ix_appraisal_goal_values_check_in", "check_in_id"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    goal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appraisal_goals.id", ondelete="CASCADE"), nullable=False
    )
    check_in_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appraisal_check_ins.id", ondelete="CASCADE"),
        nullable=False,
    )
    value: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    source_note: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    source_url: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    reported_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
