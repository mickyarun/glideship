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

"""A stage agent's run on a board card, as an :class:`AgentSubject`.

The run's reach (:mod:`.grant`) is decided when it loads: the tools its
skill declares that the board-run allowlist keeps (:mod:`.tools`), cut back
when the person behind the run lacks ``workspace:engineering`` or the board
links no repository. Its MCP token covers one card and one run and expires
with the deadline; it is revoked when the run ends. The CLI gets no built-in
tools (:mod:`.launch`). The output is a ``pending_review`` draft
(:mod:`.output`). The agent runs with no repository checkout.

A run found stopped by someone else at any step raises
:class:`AgentRunCanceledError`, so its job ends canceled. Once the Garden heard
the run start, it always hears it end: completed, or failed for a failure,
crash or cancel.
"""

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.mcp.token_grants import revoke_scoped_mcp_token
from app.models.board_enums import BoardCardDocKind
from app.schemas.boards.agent import BoardAgentRunPayload
from app.services.agents.subject import AgentLaunch, AgentPrompt, AgentRunCanceledError
from app.services.boards.agents import apply
from app.services.boards.agents.context import card_context
from app.services.boards.agents.garden import GardenRun, GardenTag
from app.services.boards.agents.grant import RunReach, mint_run_token, run_reach
from app.services.boards.agents.launch import mark_started, runner_config
from app.services.boards.agents.loading import load_refs, on_fresh_session
from app.services.boards.agents.output import save_output
from app.services.boards.agents.prompt import build_card_prompt
from app.services.boards.agents.refs import RunRefs
from app.services.boards.agents.runs import stop_reason
from app.services.boards.constants import AGENT_OUTPUT_KINDS, DEFAULT_AGENT_OUTPUT_KIND
from app.services.claude_runner import (
    NO_REPO_CONTEXT,
    ClaudeRunResult,
    MCPServerConfig,
    ProgressCallback,
)

logger = structlog.get_logger(__name__)


class CardAgentSubject:
    """One run of a stage agent on one card."""

    def __init__(self, job_id: str, payload: BoardAgentRunPayload) -> None:
        self.job_id = job_id
        self.org_id = payload.org_id
        self.run_id = payload.run_id
        self._refs: RunRefs | None = None
        self._reach: RunReach | None = None
        self._token: str | None = None
        self._garden = GardenRun()
        self._completed = False

    @property
    def refs(self) -> RunRefs:
        """The loaded run, card, board and skill."""
        assert self._refs is not None  # set by load()
        return self._refs

    @property
    def reach(self) -> RunReach:
        """What the run may read, decided at load."""
        assert self._reach is not None  # set by load()
        return self._reach

    @property
    def kind(self) -> BoardCardDocKind:
        """The document this run's skill writes."""
        return AGENT_OUTPUT_KINDS.get(self.refs.skill.agent_type, DEFAULT_AGENT_OUTPUT_KIND)

    @property
    def timeout_seconds(self) -> int:
        """The skill's own deadline, else the boards default."""
        return self.refs.skill.timeout_seconds or settings.boards.agent_timeout_seconds

    def log_phase(self, phase: str, **fields: Any) -> None:
        """Log one step under ``board_agent_phase``."""
        logger.info("board_agent_phase", phase=phase, run_id=str(self.run_id), **fields)

    async def load(self, db: AsyncSession) -> str | None:
        """Load the run's rows; a deleted skill fails the run here.

        Raises:
            AgentRunCanceledError: The run isn't pending any more, or the board's AI is off.
        """
        loaded = await load_refs(db, self.org_id, self.run_id)
        if isinstance(loaded, str):
            return loaded
        self._refs = loaded
        self._garden.tag = GardenTag.of(loaded)
        self._reach = await run_reach(db, loaded)
        self.log_phase(
            "run_loaded", skill_slug=loaded.skill.skill_slug, tools=sorted(self._reach.tools)
        )
        return None

    async def build_prompt(self, db: AsyncSession) -> AgentPrompt:
        """The skill's prompt and the card's context."""
        context = await card_context(db, self.refs.board, self.refs.card)
        repos = self.reach.repos if self.reach.code_tools else ()
        text = build_card_prompt(self.refs.skill.prompt, context, self.kind, code_repos=repos)
        return AgentPrompt(text=text, working_dir=None)

    def mcp_grant(self) -> MCPServerConfig | None:
        """A token for this card and run only, with the tools its reach allows.

        Raises:
            ScopedTokenLimitError: Too many live run tokens; the run fails.
        """
        if not settings.mcp_backend_url:
            return None
        lifetime = self.timeout_seconds + settings.boards.agent_token_grace_seconds
        self._token, config = mint_run_token(self.refs, self.reach, lifetime)
        return config

    def _revoke(self) -> None:
        if self._token is not None:
            revoke_scoped_mcp_token(self._token)
            self._token = None

    async def prepare(
        self, db: AsyncSession, prompt: AgentPrompt, mcp: MCPServerConfig | None
    ) -> AgentLaunch:
        """Mark the run running (announced on its board) and set the provider config.

        Raises:
            AgentRunCanceledError: The run was stopped before it could start.
        """
        config = runner_config(self.refs.skill, self.timeout_seconds, mcp)
        await mark_started(db, self.refs)
        self._garden.started()
        return AgentLaunch(config=config, spawn_cwd=NO_REPO_CONTEXT)

    async def review(
        self,
        db: AsyncSession,
        result: ClaudeRunResult,
        prompt: AgentPrompt,
        launch: AgentLaunch,
        progress: ProgressCallback,
    ) -> ClaudeRunResult:
        """Card runs have no repository, so nothing is retried."""
        return result

    async def handle_output(self, db: AsyncSession, output: str) -> dict[str, Any] | None:
        """The draft the tool wrote, else the reply saved as one (:func:`.output.save_output`)."""
        return await save_output(db, self.refs, self.kind, output)

    async def record_success(self, db: AsyncSession, summary: dict[str, Any] | None) -> None:
        """Settle the run completed and tell the card's assignees."""
        self._revoke()
        self._completed = await apply.finish_succeeded(db, self.refs.row, summary or {})
        if not self._completed:
            raise AgentRunCanceledError(stop_reason(self.refs.run))

    async def record_failure(self, db: AsyncSession, error: str) -> None:
        """Settle the run failed; the card stays as it was."""
        self._revoke()
        if not await apply.finish_failed(db, self.refs.row, error):
            raise AgentRunCanceledError(stop_reason(self.refs.run))
        self._garden.ended("skill_failed")

    async def record_cancel(self, reason: str) -> None:
        """Settle the run canceled on a fresh session, unless it already was."""
        self._revoke()
        await on_fresh_session(self.org_id, self.run_id, apply.finish_canceled, reason)
        self._garden.ended("skill_failed")

    async def record_crash(self, exc: Exception) -> None:
        """Settle the run failed on a fresh session (the main one was rolled back)."""
        self._revoke()
        await on_fresh_session(self.org_id, self.run_id, apply.finish_failed, str(exc))
        self._garden.ended("skill_failed")
        logger.exception("board_agent_run_failed", run_id=str(self.run_id))

    async def after_success(self) -> None:
        """Nothing more: the run's end was announced with its commit."""

    def announce(self) -> None:
        """Tell the Garden the agent finished."""
        if self._completed:
            self._garden.ended("skill_completed")
