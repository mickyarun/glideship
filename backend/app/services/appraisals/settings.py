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

"""Reading and saving the org's appraisal settings; the only writer."""

import uuid
from typing import Any

import structlog
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.organization import OrganizationRepository
from app.schemas.appraisal_settings import AppraisalSettings

logger = structlog.get_logger(__name__)
CONFIG_KEY = "appraisals"


def appraisal_settings(
    org_config: dict[str, Any] | None, org_id: uuid.UUID | None = None
) -> AppraisalSettings:
    """The org's settings, or the defaults if missing or unreadable."""
    raw = (org_config or {}).get(CONFIG_KEY) or {}
    try:
        return AppraisalSettings.model_validate(raw)
    except ValidationError:
        keys = sorted(raw) if isinstance(raw, dict) else type(raw).__name__
        logger.error("appraisal_settings_invalid", org_id=str(org_id), keys=keys)
        return AppraisalSettings()


async def load_appraisal_settings(db: AsyncSession, org_id: uuid.UUID) -> AppraisalSettings:
    """The org's saved settings."""
    return appraisal_settings(await OrganizationRepository(db).get_config(org_id), org_id)


async def save_appraisal_settings(
    db: AsyncSession, org_id: uuid.UUID, settings: AppraisalSettings
) -> None:
    """Store the settings; running cycles keep the copy they started with."""
    await OrganizationRepository(db).set_config_section(
        org_id, CONFIG_KEY, settings.model_dump(mode="json")
    )
