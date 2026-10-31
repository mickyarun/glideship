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

from app.config_board_activity import BoardActivitySettings
from app.config_board_agents import BoardAgentSettings
from app.config_board_imports import BoardImportSettings


class BoardsConfig(BoardImportSettings, BoardAgentSettings, BoardActivitySettings):
    """Tunables for team boards: shape, ordering, history, imports, agents and reminders."""

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
    aging_days: int = Field(
        default=14,
        gt=0,
        description="Days since a card first entered in progress before it is aging.",
    )
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
        default=time(9, 0),
        description="Local due-reminder time unless the org sets boards.due_reminder_time.",
    )
    due_reminder_tick_seconds: int = Field(
        default=60, gt=0, description="How often the due-reminder scheduler wakes."
    )
    due_reminder_max_cards: int = Field(
        default=15, gt=0, description="Cards one due-reminder message lists before 'and N more'."
    )
    due_reminder_window_minutes: int = Field(
        default=180,
        gt=0,
        description="How long after the fire time reminders still go out (clipped at midnight).",
    )
    due_reminder_lookahead_hours: int = Field(
        default=48,
        gt=0,
        description="Cards due within this many hours put an org on the scheduler's list.",
    )
    due_reminder_max_retries: int = Field(
        default=3, ge=0, description="Times a failed or stuck reminder DM is sent again."
    )
    due_reminder_stale_minutes: int = Field(
        default=30, gt=0, description="A claim still unfinished after this is retried."
    )
    due_reminder_org_concurrency: int = Field(
        default=4, gt=0, description="Orgs whose reminders are sent at the same time."
    )
    due_reminder_dm_concurrency: int = Field(
        default=2, gt=0, description="Reminder DMs in flight at once within one org."
    )
    due_reminder_dm_interval_seconds: float = Field(
        default=1.2,
        ge=0,
        description="Least gap between reminder DMs in one org (Slack Tier 3 is ~50/min).",
    )
    move_board_limit: int = Field(
        default=30, gt=0, description="Cards one person may move between boards per window."
    )
    move_board_window_seconds: int = Field(
        default=60, gt=0, description="The window move_board_limit counts over."
    )
    handover_similar_limit: int = Field(
        default=5, gt=0, description="Similar open BUDs a handover preview lists."
    )
    handover_link_search_limit: int = Field(
        default=20, gt=0, description=r"Open BUDs one search of the BUD list (\`?q=\`) returns."
    )
    handover_history_limit: int = Field(
        default=10, gt=0, description="Send-backs and re-handovers each handover lists."
    )
    handover_embedding_cache_size: int = Field(
        default=256, gt=0, description="Preview embeddings kept for the confirm that follows."
    )
    handover_embedding_cache_seconds: int = Field(
        default=900, gt=0, description="How long a preview's embedding is kept for its confirm."
    )

    @model_validator(mode="after")
    def _epsilon_below_gap(self) -> "BoardsConfig":
        """A rebalance threshold at or above the gap would rebalance on every insert."""
        if self.position_epsilon >= self.position_gap:
            raise ValueError("BOARDS_POSITION_EPSILON must be smaller than BOARDS_POSITION_GAP")
        return self
