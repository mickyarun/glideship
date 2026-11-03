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

"""Who gets the daily follow-ups DM, and when each person asked for it."""

import uuid
from collections.abc import Collection
from dataclasses import dataclass
from datetime import time

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.employee_profile import EmployeeProfile
from app.models.followup_settings import FollowupSettings
from app.models.leave_policy import LeavePolicy
from app.models.organization import Organization
from app.models.user import OrgToUser, User


@dataclass(frozen=True)
class Subscriber:
    """One opted-in, Slack-linked person and their saved schedule in one org."""

    org_id: uuid.UUID
    user_id: uuid.UUID
    send_time: time
    timezone: str
    weekdays_only: bool


async def followup_subscribers(db: AsyncSession, category: str) -> list[Subscriber]:
    """Everyone across all orgs who turned ``category`` on and is linked to Slack.

    The scheduler's starting point: it works out who is due from this one
    read before opening a session for any org. Only orgs where they turned
    it on count, and ``category`` (opt-in) must be on too, as the sender
    checks it.
    """
    rows = await db.execute(
        select(
            FollowupSettings.org_id,
            FollowupSettings.user_id,
            FollowupSettings.send_time,
            FollowupSettings.timezone,
            FollowupSettings.weekdays_only,
        )
        .join(User, User.id == FollowupSettings.user_id)
        .join(
            OrgToUser,
            and_(OrgToUser.user_id == User.id, OrgToUser.org_id == FollowupSettings.org_id),
        )
        .where(
            FollowupSettings.enabled.is_(True),
            User.is_active.is_(True),
            User.slack_id.is_not(None),
            User.notification_prefs[category].astext == "true",
        )
    )
    return [Subscriber(*row) for row in rows.all()]


async def enabled_anywhere(db: AsyncSession, user_id: uuid.UUID) -> bool:
    """Whether the person has the follow-ups on in any of their orgs."""
    found = await db.execute(
        select(FollowupSettings.id)
        .where(FollowupSettings.user_id == user_id, FollowupSettings.enabled.is_(True))
        .limit(1)
    )
    return found.first() is not None


class FollowupSettingsRepository:
    """Follow-ups schedules in one org."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID) -> None:
        """Initialize the repository."""
        self._db = db
        self._org = org_id

    async def get(self, user_id: uuid.UUID) -> FollowupSettings | None:
        """The person's saved schedule, if they saved one."""
        row = await self._db.execute(
            select(FollowupSettings).where(
                FollowupSettings.org_id == self._org, FollowupSettings.user_id == user_id
            )
        )
        return row.scalar_one_or_none()

    async def weekdays_only(self, user_ids: Collection[uuid.UUID]) -> dict[uuid.UUID, bool]:
        """Each of ``user_ids`` with the follow-ups on here, and whether it's weekdays only."""
        if not user_ids:
            return {}
        rows = await self._db.execute(
            select(FollowupSettings.user_id, FollowupSettings.weekdays_only).where(
                FollowupSettings.org_id == self._org,
                FollowupSettings.user_id.in_(list(user_ids)),
                FollowupSettings.enabled.is_(True),
            )
        )
        return {row[0]: row[1] for row in rows.all()}

    async def upsert(
        self,
        user_id: uuid.UUID,
        *,
        enabled: bool,
        send_time: time,
        timezone: str,
        weekdays_only: bool,
    ) -> None:
        """Save whether it's on here and the schedule, replacing any earlier row."""
        values = {
            "enabled": enabled,
            "send_time": send_time,
            "timezone": timezone,
            "weekdays_only": weekdays_only,
        }
        await self._db.execute(
            insert(FollowupSettings)
            .values(id=uuid.uuid4(), org_id=self._org, user_id=user_id, **values)
            .on_conflict_do_update(
                constraint="uq_followup_settings_org_user",
                set_={**values, "updated_at": func.now()},
            )
        )

    async def policy_timezone(self, user_id: uuid.UUID) -> str | None:
        """The person's leave policy's timezone, else the org default policy's."""
        own = aliased(LeavePolicy)
        default = aliased(LeavePolicy)
        row = await self._db.execute(
            select(own.timezone, default.timezone)
            .select_from(Organization)
            .outerjoin(
                EmployeeProfile,
                and_(EmployeeProfile.org_id == self._org, EmployeeProfile.user_id == user_id),
            )
            .outerjoin(own, own.id == EmployeeProfile.leave_policy_id)
            .outerjoin(default, and_(default.org_id == self._org, default.is_default.is_(True)))
            .where(Organization.id == self._org)
        )
        found = row.first()
        return (found[0] or found[1]) if found else None
