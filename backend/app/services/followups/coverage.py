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

"""Whose due cards the daily follow-ups carry instead of the morning card reminder."""

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.followup_settings import FollowupSettingsRepository
from app.repositories.user import UserRepository
from app.services.followups.schedule import skips_day
from app.services.notifications import (
    NotificationCategory,
    category_default,
    category_permission,
)

CATEGORY = NotificationCategory.DAILY_FOLLOWUPS


async def covered_by_followups(
    db: AsyncSession, org_id: uuid.UUID, user_ids: set[uuid.UUID], day: date
) -> set[uuid.UUID]:
    """Those of ``user_ids`` whose follow-ups DM goes out on ``day`` and would reach them.

    A weekdays-only schedule doesn't cover weekends, so those people keep
    the card reminder then.
    """
    if not user_ids:
        return set()
    pairs = await UserRepository(db).list_slack_recipients(
        org_id,
        category=CATEGORY,
        default_enabled=category_default(CATEGORY),
        permission=category_permission(CATEGORY),
        user_ids=user_ids,
    )
    opted = {user_id for user_id, _slack_id in pairs}
    weekdays = await FollowupSettingsRepository(db, org_id=org_id).weekdays_only(opted)
    return {user_id for user_id, only in weekdays.items() if not skips_day(only, day)}
