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

"""When one person wants their daily follow-ups DM.

Whether it's on is per org, here in ``enabled``. The person's
``daily_followups`` notification choice (opt-in) mirrors whether it's on
in any of their orgs, so the shared recipient filter lets the DM through.
"""

import uuid
from datetime import time

from sqlalchemy import Boolean, ForeignKey, String, Time, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel

TIMEZONE_LENGTH = 64


class FollowupSettings(BaseModel):
    """One person's follow-ups schedule in one org."""

    __tablename__ = "followup_settings"
    __table_args__ = (UniqueConstraint("org_id", "user_id", name="uq_followup_settings_org_user"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE", name="fk_followup_settings_org"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE", name="fk_followup_settings_user"),
        nullable=False,
    )
    # Local wall-clock time in ``timezone``.
    send_time: Mapped[time] = mapped_column(Time, nullable=False)
    # IANA name, e.g. "Europe/London"; checked against zoneinfo on save.
    timezone: Mapped[str] = mapped_column(String(TIMEZONE_LENGTH), nullable=False)
    weekdays_only: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
