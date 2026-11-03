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

"""Request and response bodies for a person's daily follow-ups settings."""

from datetime import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator

from app.models.followup_settings import TIMEZONE_LENGTH


class FollowupSettingsRead(BaseModel):
    """Whether the DM is on, and when it goes out.

    ``timezone`` is the saved one, else the person's leave policy's; None
    when neither exists, so the browser's own zone can be offered instead.
    """

    enabled: bool
    send_time: time
    timezone: str | None
    weekdays_only: bool


class FollowupSettingsUpdate(BaseModel):
    """The whole schedule, saved together with the on/off switch."""

    enabled: bool
    send_time: time
    timezone: str = Field(..., min_length=1, max_length=TIMEZONE_LENGTH)
    weekdays_only: bool = True

    @field_validator("timezone")
    @classmethod
    def _known_zone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"Unknown timezone: {value}") from exc
        return value

    @field_validator("send_time")
    @classmethod
    def _whole_minutes(cls, value: time) -> time:
        return value.replace(second=0, microsecond=0, tzinfo=None)
