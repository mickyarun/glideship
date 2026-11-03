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

"""Who gets the daily follow-ups DM, and when each person wants it.

It's on in every org a person belongs to until they turn it off there, so a
missing ``followup_settings`` row means on, with the default schedule.
"""

import uuid
from collections.abc import Collection
from dataclasses import dataclass
from datetime import time

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.followup_settings import FollowupSettings
from app.models.organization import Organization
from app.models.user import OrgToUser, User
from app.repositories.followup_zone import ZoneParts, with_zone_parts


@dataclass(frozen=True)
class SubscriberRow:
    """One Slack-linked person with the follow-ups on in one org.

    ``saved_zone`` is None when they never saved a schedule there; the
    service then works the zone out from ``zone``.
    """

    org_id: uuid.UUID
    user_id: uuid.UUID
    send_time: time
    weekdays_only: bool
    saved_zone: str | None
    zone: ZoneParts


async def followup_subscribers(
    db: AsyncSession, category: str, *, default_time: time
) -> list[SubscriberRow]:
    """Everyone across all orgs with the follow-ups on, linked to Slack.

    The scheduler's starting point: it works out who is due from this one
    read before opening a session for any org. Without a saved schedule a
    person gets ``default_time``, weekdays only. An explicit "false" for
    ``category`` mutes it too, as the sender checks it.
    """
    base = (
        select(
            OrgToUser.org_id,
            OrgToUser.user_id,
            func.coalesce(FollowupSettings.send_time, default_time),
            func.coalesce(FollowupSettings.weekdays_only, True),
            FollowupSettings.timezone,
        )
        .join(User, User.id == OrgToUser.user_id)
        .join(Organization, Organization.id == OrgToUser.org_id)
        .outerjoin(
            FollowupSettings,
            and_(
                FollowupSettings.org_id == OrgToUser.org_id,
                FollowupSettings.user_id == OrgToUser.user_id,
            ),
        )
    )
    stmt, zone_columns = with_zone_parts(base, OrgToUser.org_id, OrgToUser.user_id)
    rows = await db.execute(
        stmt.add_columns(*zone_columns).where(
            func.coalesce(FollowupSettings.enabled, True).is_(True),
            User.is_active.is_(True),
            User.slack_id.is_not(None),
            func.coalesce(User.notification_prefs[category].astext, "true") != "false",
        )
    )
    return [
        SubscriberRow(
            org_id=org_id,
            user_id=user_id,
            send_time=send_time,
            weekdays_only=weekdays_only,
            saved_zone=saved_zone,
            zone=ZoneParts(own_policy, default_policy, org_config),
        )
        for (
            org_id,
            user_id,
            send_time,
            weekdays_only,
            saved_zone,
            own_policy,
            default_policy,
            org_config,
        ) in rows.all()
    ]


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
        """Each of ``user_ids`` with the follow-ups on here, and whether it's weekdays only.

        People who never saved a schedule are on, weekdays only.
        """
        if not user_ids:
            return {}
        rows = await self._db.execute(
            select(
                FollowupSettings.user_id, FollowupSettings.enabled, FollowupSettings.weekdays_only
            ).where(
                FollowupSettings.org_id == self._org,
                FollowupSettings.user_id.in_(list(user_ids)),
            )
        )
        result = dict.fromkeys(user_ids, True)
        for user_id, enabled, only in rows.all():
            if enabled:
                result[user_id] = only
            else:
                del result[user_id]
        return result

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

    async def zone_parts(self, user_id: uuid.UUID) -> ZoneParts:
        """What the person's default zone in this org is worked out from."""
        base = select().select_from(Organization).where(Organization.id == self._org)
        stmt, zone_columns = with_zone_parts(base, self._org, user_id)
        row = await self._db.execute(stmt.add_columns(*zone_columns))
        found = row.first()
        return ZoneParts(*found) if found else ZoneParts(None, None, None)
