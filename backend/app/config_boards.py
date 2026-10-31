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

"""Tunables for team boards, read from ``BOARDS_*`` environment variables."""

from datetime import time

from pydantic import Field, model_validator
from pydantic_settings import SettingsConfigDict

from app.config_board_imports import BoardImportSettings


class BoardsConfig(BoardImportSettings):
    """Tunables for team boards: shape, ordering, history, imports and reminders."""

    model_config = SettingsConfigDict(env_prefix="BOARDS_", env_file=".env", extra="ignore")

    max_stages_per_board: int = Field(default=8, gt=0, description="Soft cap on stages.")
    stage_page_size: int = Field(default=50, gt=0, description="Cards per stage page.")
    position_gap: float = Field(default=1024.0, gt=0, description="Spacing between cards.")
    position_epsilon: float = Field(
        default=1e-6, gt=0, description="A gap below this rebalances the stage."
    )
    edit_coalesce_seconds: int = Field(
        default=300, ge=0, description="Edits by one person within this window merge."
    )
    aging_days: int = Field(default=14, gt=0, description="Idle days before a card is aging.")
    recent_done_days: int = Field(
        default=7, gt=0, description="Days the boards list counts finished cards over."
    )
    metrics_window_days: int = Field(default=90, gt=0, description="Board metrics look-back.")
    switcher_other_limit: int = Field(
        default=20, gt=0, description="Boards listed under 'other' in the switcher."
    )
    switcher_recent_limit: int = Field(
        default=10, gt=0, description="Boards listed under 'recent' in the switcher."
    )
    prefs_touch_interval_seconds: int = Field(
        default=300, ge=0, description="Minimum gap between last-opened writes."
    )
    filters_max_bytes: int = Field(
        default=4096, gt=0, description="Largest saved filter set, as JSON."
    )
    events_page_size: int = Field(default=50, gt=0, description="Card history entries per page.")
    comments_page_size: int = Field(default=50, gt=0, description="Comments per page.")
    versions_page_size: int = Field(default=50, gt=0, description="Document versions per page.")
    attachment_max_file_mb: int = Field(
        default=10, gt=0, description="Largest file one card attachment may be."
    )
    attachment_max_files: int = Field(
        default=20, gt=0, description="Files one card may hold; links don't count."
    )
    due_reminder_default_time: time = Field(
        default=time(9, 0), description="Local time due reminders go out."
    )

    @model_validator(mode="after")
    def _epsilon_below_gap(self) -> "BoardsConfig":
        """A rebalance threshold at or above the gap would rebalance on every insert."""
        if self.position_epsilon >= self.position_gap:
            raise ValueError("BOARDS_POSITION_EPSILON must be smaller than BOARDS_POSITION_GAP")
        return self
