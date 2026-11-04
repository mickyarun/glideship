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

"""Read and save one person's daily follow-ups settings for the settings page."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.repositories.followup_settings import FollowupSettingsRepository
from app.repositories.user import UserRepository
from app.schemas.followups import FollowupSettingsRead, FollowupSettingsUpdate
from app.services.followups.zone import default_zone
from app.services.notifications import NotificationCategory, is_category_enabled

CATEGORY = NotificationCategory.DAILY_FOLLOWUPS


async def read_settings(
    db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID
) -> FollowupSettingsRead:
    """The person's choice, with the defaults filled in where they haven't chosen.

    On or off is per org, and on until they turn it off. A "false" left in
    their notification choices from before shows as off, since it mutes the
    DM, until they turn it on again.
    """
    prefs = await UserRepository(db).get_notification_prefs(user_id)
    allowed = is_category_enabled(prefs, CATEGORY)
    repo = FollowupSettingsRepository(db, org_id=org_id)
    saved = await repo.get(user_id)
    if saved is not None:
        return FollowupSettingsRead(
            enabled=saved.enabled and allowed,
            send_time=saved.send_time,
            timezone=saved.timezone,
            weekdays_only=saved.weekdays_only,
        )
    return FollowupSettingsRead(
        enabled=allowed,
        send_time=settings.followups.default_time,
        timezone=default_zone(await repo.zone_parts(user_id), org_id),
        weekdays_only=True,
    )


async def save_settings(
    db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID, body: FollowupSettingsUpdate
) -> FollowupSettingsRead:
    """Save this org's switch and schedule.

    The per-org row is the only switch, so any account-wide choice for the
    category is cleared rather than left to mute other orgs.
    """
    await FollowupSettingsRepository(db, org_id=org_id).upsert(
        user_id,
        enabled=body.enabled,
        send_time=body.send_time,
        timezone=body.timezone,
        weekdays_only=body.weekdays_only,
    )
    users = UserRepository(db)
    prefs = dict(await users.get_notification_prefs(user_id))
    if prefs.pop(CATEGORY.value, None) is not None:
        await users.set_notification_prefs(user_id, prefs)
    return FollowupSettingsRead(
        enabled=body.enabled,
        send_time=body.send_time,
        timezone=body.timezone,
        weekdays_only=body.weekdays_only,
    )
