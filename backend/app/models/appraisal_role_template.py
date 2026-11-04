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

"""What appraisals mean for one kind of role, edited by HR.

Which departments and designations it matches, what each check-in
heading means, which fact sources apply, a goal library, and market
trends (AI-drafted with sources, used only once HR approves them). Not
encrypted: templates describe roles, not people.
"""

import uuid
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.appraisal_enums import FactSource, TrendsStatus, pg_enum
from app.models.base import BaseModel


class AppraisalRoleTemplate(BaseModel):
    """One role template; one per org is the general fallback."""

    __tablename__ = "appraisal_role_templates"
    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_appraisal_role_templates_name"),
        Index(
            "uq_appraisal_role_templates_default",
            "org_id",
            unique=True,
            postgresql_where="is_default",
        ),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    match_departments: Mapped[list[str]] = mapped_column(
        ARRAY(String(150)), nullable=False, default=list
    )
    match_designations: Mapped[list[str]] = mapped_column(
        ARRAY(String(150)), nullable=False, default=list
    )
    # Heading → one line on what it means for this role.
    heading_meanings: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False, default=dict)
    fact_sources: Mapped[list[FactSource]] = mapped_column(
        ARRAY(pg_enum(FactSource, "appraisal_fact_source")), nullable=False, default=list
    )
    # Each: title, measure, measure_source, trend_id.
    goal_library: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    # Each: id, text, source_url, as_of.
    trends: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    trends_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trends_status: Mapped[TrendsStatus] = mapped_column(
        pg_enum(TrendsStatus, "appraisal_trends_status"),
        nullable=False,
        default=TrendsStatus.DRAFT,
    )
    trends_approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    ai_drafting: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
