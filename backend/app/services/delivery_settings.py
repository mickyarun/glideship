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

"""The Delivery board's settings: the only reader and writer of ``config["delivery"]``.

A corrupt stored section reads as the defaults (AI on), logged, so one bad
org never stops BUD agents elsewhere or fails a request.
"""

import uuid
from typing import Any, Final

import structlog
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.organization import OrganizationRepository
from app.schemas.delivery_settings import DeliverySettings, DeliverySettingsUpdate

logger = structlog.get_logger(__name__)

DELIVERY_CONFIG_KEY: Final = "delivery"


def read_delivery_settings(org_config: dict[str, Any] | None) -> DeliverySettings:
    """The settings stored in an org's ``config``, defaults filling any gap."""
    raw = (org_config or {}).get(DELIVERY_CONFIG_KEY) or {}
    try:
        return DeliverySettings.model_validate(raw)
    except ValidationError as exc:
        logger.error("delivery_settings_invalid", raw_keys=list(raw), error=str(exc))
        return DeliverySettings()


async def get_delivery_settings(db: AsyncSession, org_id: uuid.UUID) -> DeliverySettings:
    """The org's Delivery settings."""
    return read_delivery_settings(await OrganizationRepository(db).get_config(org_id))


async def delivery_ai_enabled(db: AsyncSession, org_id: uuid.UUID) -> bool:
    """Whether BUD stage agents may start in this org."""
    return (await get_delivery_settings(db, org_id)).ai_enabled


async def update_delivery_settings(
    db: AsyncSession, org_id: uuid.UUID, body: DeliverySettingsUpdate
) -> DeliverySettings:
    """Apply ``body`` to the stored settings; the caller commits."""
    current = await get_delivery_settings(db, org_id)
    merged = current.model_copy(update=body.model_dump(exclude_none=True))
    await OrganizationRepository(db).set_config_section(
        org_id, DELIVERY_CONFIG_KEY, merged.model_dump()
    )
    logger.info("delivery_settings_updated", org_id=str(org_id), ai_enabled=merged.ai_enabled)
    return merged
