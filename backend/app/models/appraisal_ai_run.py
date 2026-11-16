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

"""A record of one AI run on someone's appraisal: what it saw and what it wrote.

So anyone reviewing a summary can see the prompt, the model, the facts it
cited and the raw output. Runs have no human actor, so they live here
rather than in the audit log. Prompt and output are HR-key ciphertext.
"""

import uuid

from sqlalchemy import ForeignKey, Index, LargeBinary, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.appraisal_enums import DraftKind, pg_enum
from app.models.base import BaseModel


class AppraisalAiRun(BaseModel):
    """One run; the time is ``created_at``."""

    __tablename__ = "appraisal_ai_runs"
    __table_args__ = (Index("ix_appraisal_ai_runs_record", "org_id", "record_id"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employee_profiles.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[DraftKind] = mapped_column(
        pg_enum(DraftKind, "appraisal_draft_kind"), nullable=False
    )
    # The check-in or appraisal it drafted for.
    record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    fact_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    prompt: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    output: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    # An error code when it failed, never the provider's message.
    error: Mapped[str | None] = mapped_column(String(60), nullable=True)
