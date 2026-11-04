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

"""A link an employee adds to a check-in: a ticket, a doc, a published page.

Shown as "added by you" so nobody mistakes it for something Glideship
recorded. URL and title are encrypted: a link can name a customer.
"""

import uuid

from sqlalchemy import ForeignKey, Index, LargeBinary
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.appraisal_enums import EvidenceHeading, pg_enum
from app.models.base import BaseModel


class AppraisalEvidenceLink(BaseModel):
    """One link on one check-in."""

    __tablename__ = "appraisal_evidence_links"
    __table_args__ = (Index("ix_appraisal_evidence_links_check_in", "check_in_id"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employee_profiles.id", ondelete="CASCADE"), nullable=False
    )
    check_in_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appraisal_check_ins.id", ondelete="CASCADE"),
        nullable=False,
    )
    url: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    title: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    heading: Mapped[EvidenceHeading] = mapped_column(
        pg_enum(EvidenceHeading, "appraisal_evidence_heading"), nullable=False
    )
    goal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appraisal_goals.id", ondelete="SET NULL"), nullable=True
    )
    added_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
