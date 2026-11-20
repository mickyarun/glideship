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

"""DTOs for the daily who's-out Slack post."""

from typing import Annotated, Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.settings import validate_optional_timezone


class LeaveDigestSettings(BaseModel):
    """Org-wide settings, stored under ``org.config["leave_digest"]``."""

    enabled: bool = False
    # Slack channel ids (C… public, G… private); the bot must be in each.
    channel_ids: list[Annotated[str, Field(max_length=30, pattern=r"^[CG][A-Z0-9]{6,}$")]] = Field(
        default_factory=list, max_length=10
    )
    post_time: str = Field("09:30", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    # None follows the default leave policy's timezone.
    timezone: str | None = Field(None, max_length=64)

    @model_validator(mode="before")
    @classmethod
    def _single_channel(cls, data: Any) -> Any:
        """Settings saved before there could be several hold one ``channel_id``."""
        if isinstance(data, dict) and "channel_ids" not in data and data.get("channel_id"):
            return {**data, "channel_ids": [data["channel_id"]]}
        return data

    @field_validator("channel_ids")
    @classmethod
    def _distinct(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))

    @field_validator("timezone")
    @classmethod
    def _timezone(cls, value: str | None) -> str | None:
        return validate_optional_timezone(value)


class DigestTestResult(BaseModel):
    """What a test post did: Slack's error code if it failed, and the text."""

    ok: bool
    error: str | None
    text: str
