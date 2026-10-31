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

"""What an agent run is about: the ``AgentSubject`` protocol and its values.

:func:`app.services.agents.executor.execute_agent_run` owns the run's shape
(job progress, one database session, the provider call, the cancel and crash
paths). A subject owns everything that depends on what the agent works on:
loading its rows, the prompt, the MCP grant, saving the output and recording
how the run ended. BUD stage agents and board card agents are the two subjects.
"""

import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.claude_runner import (
    ClaudeRunnerConfig,
    ClaudeRunResult,
    MCPServerConfig,
    ProgressCallback,
)


@dataclass(frozen=True)
class AgentRunRef:
    """The ids every run carries: whose org it runs for, and its own row."""

    org_id: uuid.UUID
    run_id: uuid.UUID


@dataclass(frozen=True)
class AgentPrompt:
    """The prompt text and the repo checkout it runs against, if any."""

    text: str
    working_dir: str | None


@dataclass(frozen=True)
class AgentLaunch:
    """How the provider is called: its config and the directory it starts in."""

    config: ClaudeRunnerConfig
    spawn_cwd: str


class AgentSubject(Protocol):
    """One kind of thing an agent works on (a BUD stage, a board card)."""

    def log_phase(self, phase: str, **fields: Any) -> None:
        """Log one step of the run under the subject's own event name."""
        ...

    async def load(self, db: AsyncSession) -> str | None:
        """Load the run's rows; return an error to fail the job, or ``None`` to go on."""
        ...

    async def build_prompt(self, db: AsyncSession) -> AgentPrompt:
        """Build the prompt from the loaded rows."""
        ...

    def mcp_grant(self) -> MCPServerConfig | None:
        """The MCP server config, carrying a token whose grant covers this run's tools."""
        ...

    async def prepare(
        self, db: AsyncSession, prompt: AgentPrompt, mcp: MCPServerConfig | None
    ) -> AgentLaunch:
        """Record that the run started and settle how the provider is called."""
        ...

    async def review(
        self,
        db: AsyncSession,
        result: ClaudeRunResult,
        prompt: AgentPrompt,
        launch: AgentLaunch,
        progress: ProgressCallback,
    ) -> ClaudeRunResult:
        """Look at the provider's result once; may run it again (e.g. on a git auth failure)."""
        ...

    async def handle_output(self, db: AsyncSession, output: str) -> dict[str, Any] | None:
        """Save the agent's output; return the run's result summary."""
        ...

    async def record_success(self, db: AsyncSession, summary: dict[str, Any] | None) -> None:
        """Mark the run completed and commit."""
        ...

    async def record_failure(self, db: AsyncSession, error: str) -> None:
        """Mark the run failed after the provider reported a failure, and commit."""
        ...

    async def record_cancel(self, reason: str) -> None:
        """Mark the run failed or canceled on its own session after a cancel."""
        ...

    async def record_crash(self, exc: Exception) -> None:
        """Mark the run failed on its own session after an unexpected error, and log it."""
        ...

    async def after_success(self) -> None:
        """Side effects once the session is closed, before the job reads completed."""
        ...

    def announce(self) -> None:
        """Last publishes once the job reads completed."""
        ...
