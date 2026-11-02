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

"""Tunables for BUD stage agents (``BUD_AGENT_*`` variables)."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BudAgentConfig(BaseSettings):
    """BUD stage-agent tunables."""

    model_config = SettingsConfigDict(env_prefix="BUD_AGENT_", env_file=".env", extra="ignore")

    timeout_seconds: int = Field(
        default=600, gt=0, description="A BUD stage agent run's wall-clock deadline."
    )
