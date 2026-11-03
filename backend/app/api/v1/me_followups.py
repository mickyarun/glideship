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

"""The signed-in person's daily follow-ups DM: on or off, and when it arrives."""

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.followups import FollowupSettingsRead, FollowupSettingsUpdate
from app.services.followups.settings import read_settings, save_settings

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/me", tags=["me"])


@router.get("/followups", response_model=FollowupSettingsRead)
async def get_my_followups(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FollowupSettingsRead:
    """The caller's follow-ups settings; off until they turn it on."""
    return await read_settings(db, current_user.org_id, current_user.id)


@router.put("/followups", response_model=FollowupSettingsRead)
async def put_my_followups(
    body: FollowupSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FollowupSettingsRead:
    """Turn the caller's follow-ups on or off and set when they arrive."""
    saved = await save_settings(db, current_user.org_id, current_user.id, body)
    logger.info(
        "followup_settings_updated",
        org_id=str(current_user.org_id),
        user_id=str(current_user.id),
        enabled=body.enabled,
    )
    return saved
