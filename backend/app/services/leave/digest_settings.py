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

"""Reading and saving the daily who's-out post settings."""

import uuid
from datetime import tzinfo
from typing import Any

import structlog
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.leave_policy import LeavePolicyRepository
from app.repositories.organization import OrganizationRepository
from app.schemas.leave_digest import LeaveDigestSettings
from app.services.leave.policies import ensure_default_policy
from app.services.org_settings import get_presence_settings
from app.services.quiz_schedule_math import resolve_zone

logger = structlog.get_logger(__name__)
CONFIG_KEY = "leave_digest"


def digest_settings(
    org_config: dict[str, Any] | None, org_id: uuid.UUID | None = None
) -> LeaveDigestSettings:
    """The org's settings, or defaults (off) if missing or unreadable.

    Never raises: one bad org must not stop the scheduler for every other.
    """
    raw = (org_config or {}).get(CONFIG_KEY) or {}
    try:
        return LeaveDigestSettings.model_validate(raw)
    except ValidationError:
        keys = sorted(raw) if isinstance(raw, dict) else type(raw).__name__
        logger.error("leave_digest_settings_invalid", org_id=str(org_id), keys=keys)
        return LeaveDigestSettings()


async def load_digest_settings(db: AsyncSession, org_id: uuid.UUID) -> LeaveDigestSettings:
    """The org's saved settings."""
    return digest_settings(await OrganizationRepository(db).get_config(org_id), org_id)


async def save_digest_settings(
    db: AsyncSession, org_id: uuid.UUID, settings: LeaveDigestSettings
) -> None:
    """Store the settings on the org."""
    await OrganizationRepository(db).set_config_section(
        org_id, CONFIG_KEY, settings.model_dump(mode="json")
    )


async def digest_zone(
    db: AsyncSession, org_id: uuid.UUID, settings: LeaveDigestSettings
) -> tzinfo:
    """The post's timezone: its own, else the default leave policy's."""
    name = settings.timezone or (await ensure_default_policy(db, org_id)).timezone
    return resolve_zone(name)


async def org_zone(
    db: AsyncSession, org_id: uuid.UUID, org_config: dict[str, Any] | None
) -> tzinfo:
    """The zone :func:`digest_zone` resolves, without creating the default policy.

    For other daily messages (board due reminders) that follow the same
    timezone but mustn't set up leave for an org that doesn't use it. With
    no policy yet, the presence timezone the default would start from.
    """
    name = digest_settings(org_config, org_id).timezone
    if not name:
        policy = await LeavePolicyRepository(db, org_id=org_id).get_default()
        name = policy.timezone if policy else get_presence_settings(org_config).timezone
    return resolve_zone(name or "UTC")
