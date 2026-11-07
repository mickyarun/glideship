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

"""Tunables for appraisal reminders, read from ``APPRAISALS_*`` variables."""

from datetime import time

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppraisalsConfig(BaseSettings):
    """When appraisal reminder DMs go out and how fast they're sent."""

    model_config = SettingsConfigDict(env_prefix="APPRAISALS_", env_file=".env", extra="ignore")

    reminder_time: time = Field(
        default=time(10, 0), description="Local time each day's appraisal reminders go out."
    )
    reminder_tick_seconds: int = Field(
        default=300, gt=0, description="How often the reminder scheduler wakes."
    )
    reminder_window_minutes: int = Field(
        default=360,
        gt=0,
        description="How long after the send time reminders still go (clipped at midnight).",
    )
    max_retries: int = Field(
        default=3, ge=0, description="Times a failed or stuck reminder DM is sent again."
    )
    # Above the longest send of one kind in a large org, so a second instance
    # never takes over a claim that is still being sent.
    stale_minutes: int = Field(
        default=90, gt=0, description="A claim still unfinished after this is retried."
    )
    org_concurrency: int = Field(
        default=4, gt=0, description="Orgs whose reminders are sent at the same time."
    )
    dm_concurrency: int = Field(
        default=2, gt=0, description="Reminder DMs in flight at once within one org."
    )
    dm_interval_seconds: float = Field(
        default=1.2, ge=0, description="Least gap between reminder DMs in one org."
    )
