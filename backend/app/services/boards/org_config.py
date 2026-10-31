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

"""Reading the org's board settings, falling back to ``BoardsConfig``."""

import uuid
from datetime import time
from typing import Any

import structlog
from pydantic import ValidationError

from app.config import settings
from app.schemas.boards.org_settings import BoardsOrgSettings

logger = structlog.get_logger(__name__)
CONFIG_KEY = "boards"


def boards_org_settings(
    org_config: dict[str, Any] | None, org_id: uuid.UUID | None = None
) -> BoardsOrgSettings:
    """The org's board settings, or none set when missing or unreadable.

    Never raises: one bad org must not stop a scheduler for every other.
    """
    raw = (org_config or {}).get(CONFIG_KEY) or {}
    try:
        return BoardsOrgSettings.model_validate(raw)
    except ValidationError:
        keys = sorted(raw) if isinstance(raw, dict) else type(raw).__name__
        logger.error("boards_org_settings_invalid", org_id=str(org_id), keys=keys)
        return BoardsOrgSettings()


def due_reminder_time(org_config: dict[str, Any] | None, org_id: uuid.UUID | None = None) -> time:
    """When the org's due reminders go out, in its local time."""
    chosen = boards_org_settings(org_config, org_id).due_reminder_time
    return chosen or settings.boards.due_reminder_default_time
