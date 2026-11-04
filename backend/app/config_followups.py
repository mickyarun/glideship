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

"""Tunables for the opt-in daily follow-ups DM, read from ``FOLLOWUPS_*`` variables."""

from datetime import time

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FollowupsConfig(BaseSettings):
    """When the daily follow-ups go out, what they hold, and how fast they're sent."""

    model_config = SettingsConfigDict(env_prefix="FOLLOWUPS_", env_file=".env", extra="ignore")

    default_time: time = Field(
        default=time(9, 0), description="Local send time for someone who hasn't picked one."
    )
    tick_seconds: int = Field(default=60, gt=0, description="How often the scheduler wakes.")
    window_minutes: int = Field(
        default=180,
        gt=0,
        description="How long after the send time the DM still goes (clipped at midnight).",
    )
    soon_days: int = Field(
        default=2, ge=0, description="Days after today whose items show under 'Coming up'."
    )
    # Each item is up to three blocks and Slack allows 50 per message.
    max_items: int = Field(
        default=15, gt=0, le=15, description="Items one message lists before 'and N more'."
    )
    comment_chars: int = Field(
        default=200, gt=0, description="Longest last-comment excerpt shown under an item."
    )
    max_retries: int = Field(
        default=3, ge=0, description="Times a failed or stuck follow-ups DM is sent again."
    )
    stale_minutes: int = Field(
        default=30, gt=0, description="A claim still unfinished after this is retried."
    )
    org_concurrency: int = Field(
        default=4, gt=0, description="Orgs whose follow-ups are sent at the same time."
    )
    dm_concurrency: int = Field(
        default=2, gt=0, description="Follow-up DMs in flight at once within one org."
    )
    dm_interval_seconds: float = Field(
        default=1.2,
        ge=0,
        description="Least gap between follow-up DMs in one org (Slack Tier 3 is ~50/min).",
    )
