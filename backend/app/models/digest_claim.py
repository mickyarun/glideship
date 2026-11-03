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

"""One row per person per local day for each kind of daily personal message.

The unique (org, kind, user, day) row is the claim: whichever scheduler
tick inserts it first writes the in-app notification and sends, so a
restart, a second tick or a second instance never writes it twice. A
failed or stuck Slack message is re-claimed by a later tick (``attempts``
counts those retries), which sends the DM again but no second in-app row.
"""

import uuid
from datetime import date
from enum import StrEnum

from sqlalchemy import Date, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel
from app.models.board_enums import pg_enum


class DigestClaimKind(StrEnum):
    """Which daily message a claim is for."""

    BOARD_DUE = "board_due"
    DAILY_FOLLOWUPS = "daily_followups"


class DigestClaimStatus(StrEnum):
    """Where the person's message for the day got to."""

    CLAIMED = "claimed"
    SENT = "sent"
    # Nothing went to Slack (not linked, muted, or Slack isn't connected);
    # the in-app notification still went out.
    SKIPPED = "skipped"
    FAILED = "failed"


class DigestClaim(BaseModel):
    """The daily message of one kind for one person on one local date."""

    __tablename__ = "digest_claims"
    __table_args__ = (
        UniqueConstraint(
            "org_id", "kind", "user_id", "local_date", name="uq_digest_claims_org_kind_user_date"
        ),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE", name="fk_digest_claims_org"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE", name="fk_digest_claims_user"),
        nullable=False,
    )
    kind: Mapped[DigestClaimKind] = mapped_column(
        pg_enum(DigestClaimKind, "digest_claim_kind"), nullable=False
    )
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[DigestClaimStatus] = mapped_column(
        pg_enum(DigestClaimStatus, "digest_claim_status"), nullable=False
    )
    # Retries taken after the first send; capped by the scheduler's setting.
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # Why the message didn't go, as a short code (never message text).
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
