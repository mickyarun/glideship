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

"""Append-only history of one goal: who changed it, how and why.

The "changed by you, from ..." line under a goal reads from here. A
database trigger refuses DELETE and any UPDATE except re-encrypting the
blobs under a new HR key, so the history can't be quietly rewritten. A
purge for an erasure request sets ``glideship.purge_goal_history`` to
``on`` for its own transaction.
"""

import uuid

from sqlalchemy import ForeignKey, Index, LargeBinary
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.appraisal_enums import GoalRevisionKind, pg_enum
from app.models.base import BaseModel


class AppraisalGoalRevision(BaseModel):
    """One change to a goal; the time is ``created_at``."""

    __tablename__ = "appraisal_goal_revisions"
    __table_args__ = (Index("ix_appraisal_goal_revisions_goal", "goal_id", "created_at"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    # No foreign keys: a cascade would be refused by the trigger, and the
    # history outlives the goal and the account, like the audit log.
    goal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    changed_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    kind: Mapped[GoalRevisionKind] = mapped_column(
        pg_enum(GoalRevisionKind, "appraisal_goal_revision_kind"), nullable=False
    )
    # Title and measure before and after, encrypted as JSON.
    before: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    after: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    reason: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
