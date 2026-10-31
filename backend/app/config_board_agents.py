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

"""Tunables for agents on board stages, part of ``BoardsConfig`` (``BOARDS_*`` variables)."""

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


class BoardAgentSettings(BaseSettings):
    """Stage-agent tunables: run limits, the run token's life and what the prompt carries."""

    stage_agents_max: int = Field(default=10, gt=0, description="Agents one stage may hold.")
    agent_timeout_seconds: int = Field(
        default=600, gt=0, description="A card run's deadline unless its skill sets one."
    )
    agent_max_turns: int = Field(
        default=20, gt=0, description="A card run's turn cap unless its skill sets one."
    )
    agent_token_grace_seconds: int = Field(
        default=120, ge=0, description="How long a run's MCP token outlives its deadline."
    )
    agent_context_comments: int = Field(
        default=30, gt=0, description="Newest comments a card run's prompt includes."
    )
    agent_runs_page_size: int = Field(
        default=20, gt=0, description="Runs the card's agent panel lists."
    )
    agent_busy_retry_after_seconds: int = Field(
        default=30, gt=0, description="Retry-After when the agent queue is full."
    )
    agent_tokens_max: int = Field(
        default=200, gt=0, description="Live card-run MCP tokens at once; more are refused."
    )
    agent_runs_per_org_max: int = Field(
        default=20, gt=0, description="Pending plus running card runs one org may have."
    )
    agent_runs_per_user_max: int = Field(
        default=5, gt=0, description="Pending plus running card runs one person may start."
    )
    agent_stale_grace_seconds: int = Field(
        default=300,
        ge=0,
        description="How long past its deadline a pending or running run counts as stale.",
    )
    agent_stale_sweep_seconds: int = Field(
        default=300, gt=0, description="How often stale card runs are swept."
    )
    agent_workers: int = Field(
        default=2,
        gt=0,
        validation_alias=AliasChoices("JOB_BOARD_AGENT_WORKERS", "BOARDS_AGENT_WORKERS"),
        description="Card runs going at once in this process.",
    )
