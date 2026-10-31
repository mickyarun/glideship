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


"""Tunables for repo activity, metrics and MCP reads on boards (``BOARDS_*`` variables)."""

from pydantic import Field
from pydantic_settings import BaseSettings


class BoardActivitySettings(BaseSettings):
    """Repo activity matching, board metrics and what the board MCP tools return."""

    repo_activity_max_commits: int = Field(
        default=20, gt=0, description="Commits of one push matched against card keys."
    )
    repo_activity_max_keys: int = Field(
        default=10, gt=0, description="Card keys one pull request or commit may name."
    )
    repo_activity_scan_chars: int = Field(
        default=4000, gt=0, description="Leading characters of a commit message scanned."
    )
    metrics_throughput_weeks: int = Field(
        default=12, gt=0, description="Weeks the throughput chart covers, this one included."
    )
    metrics_aging_list_limit: int = Field(
        default=20, gt=0, description="Oldest aging cards one board's metrics list."
    )
    mcp_cards_per_stage: int = Field(
        default=50, gt=0, description="Open cards per stage the get_board MCP tool returns."
    )
