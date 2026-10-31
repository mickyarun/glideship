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

The run's MCP token covers one card and one run, and only the card tools
plus the read tools its skill declares (``CARD_RUN_READ_TOOLS``); it expires
with the run's deadline and is revoked when the run ends. The output is a
``pending_review`` draft: written through ``write_card_doc``, or, when the
tool wasn't called, saved from the agent's reply as the skill's kind of
document. The agent runs with no repository checkout.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.mcp.token_grants import (
    InternalTokenGrant,
    create_scoped_mcp_token,
    revoke_scoped_mcp_token,
)
from app.models.board_agent import BoardAgentRunStatus
from app.models.board_enums import BoardCardDocKind
from app.repositories.board_agent_run import BoardCardAgentRunRepository
from app.repositories.board_card_doc import BoardCardDocRepository
from app.schemas.boards.agent import BoardAgentRunPayload
from app.services.agents.subject import AgentLaunch, AgentPrompt
from app.services.boards.agents import apply
from app.services.boards.agents.apply import RunRefs
from app.services.boards.agents.context import card_context
from app.services.boards.agents.drafts import write_draft
from app.services.boards.agents.loading import load_refs, on_fresh_session
from app.services.boards.agents.prompt import build_card_prompt
from app.services.boards.agents.runs import queue_run_event
from app.services.boards.constants import (
    AGENT_OUTPUT_KINDS,
    CARD_RUN_READ_TOOLS,
    CARD_RUN_TOOLS,
    DEFAULT_AGENT_OUTPUT_KIND,
)
from app.services.claude_runner import (
    NO_REPO_CONTEXT,
    ClaudeRunnerConfig,
    ClaudeRunResult,
    MCPServerConfig,
    ProgressCallback,
)

logger = structlog.get_logger(__name__)

NO_OUTPUT = "The agent finished without writing a draft."


class EmptyOutputError(Exception):
    """The agent wrote no draft and replied with nothing to save."""


class CardAgentSubject:
    """One run of a stage agent on one card."""

    def __init__(self, job_id: str, payload: BoardAgentRunPayload) -> None:
        self.job_id = job_id
        self.org_id = payload.org_id
        self.run_id = payload.run_id
        self._refs: RunRefs | None = None
        self._token: str | None = None
        self._completed = False

    @property
    def refs(self) -> RunRefs:
        """The loaded run, card, board and skill."""
        assert self._refs is not None  # set by load()
        return self._refs

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
        """Load the run's rows; a run no longer pending (or whose skill is gone) stops here."""
        loaded = await load_refs(db, self.org_id, self.run_id)
        if isinstance(loaded, str):
            return loaded
        self._refs = loaded
        self.log_phase("run_loaded", skill_slug=loaded.skill.skill_slug)
        return None

    async def build_prompt(self, db: AsyncSession) -> AgentPrompt:
        """The skill's prompt and the card's context."""
        context = await card_context(db, self.refs.board, self.refs.card)
        text = build_card_prompt(self.refs.skill.prompt, context, self.kind)
        return AgentPrompt(text=text, working_dir=None)

    def mcp_grant(self) -> MCPServerConfig | None:
        """A token for this card and run only, with the card tools and allowed read tools."""
        if not settings.mcp_backend_url:
            return None
        tools = CARD_RUN_TOOLS | (frozenset(self.refs.skill.mcp_tools) & CARD_RUN_READ_TOOLS)
        lifetime = self.timeout_seconds + settings.boards.agent_token_grace_seconds
        grant = InternalTokenGrant(
            org_id=self.org_id,
            tools=tools,
            card_id=self.refs.card.id,
            run_id=self.run_id,
            expires_at=datetime.now(UTC) + timedelta(seconds=lifetime),
        )
        self._token = create_scoped_mcp_token(grant)
        return MCPServerConfig(
            backend_url=settings.mcp_backend_url,
            mcp_token=self._token,
            tool_names=sorted(tools),
            org_id=str(self.org_id),
        )

    def _revoke(self) -> None:
        if self._token is not None:
            revoke_scoped_mcp_token(self._token)
            self._token = None

    async def prepare(
        self, db: AsyncSession, prompt: AgentPrompt, mcp: MCPServerConfig | None
    ) -> AgentLaunch:
        """Mark the run running (announced on its board) and set the provider config."""
        skill, run = self.refs.skill, self.refs.run
        config = ClaudeRunnerConfig(
            max_turns=skill.max_turns or settings.boards.agent_max_turns,
            timeout_seconds=self.timeout_seconds,
            mcp=mcp,
            model=skill.model or None,
            effort=skill.effort or None,
        )
        run.status = BoardAgentRunStatus.RUNNING
        run.started_at = datetime.now(UTC)
        await db.flush()
        queue_run_event(db, self.refs.board.id, run)
        await db.commit()
        apply.garden_event(self.refs, "skill_invoked")
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
        """The draft the tool wrote, else the reply saved as one.

        Raises:
            EmptyOutputError: No draft and an empty reply.
        """
        refs = self.refs
        await BoardCardAgentRunRepository(db, org_id=self.org_id).lock(refs.run)
        if refs.run.status is not BoardAgentRunStatus.RUNNING:
            # Canceled meanwhile (the card moved boards): save nothing.
            return None
        drafted = await BoardCardDocRepository(db, org_id=self.org_id).written_by_run(self.run_id)
        if drafted is not None:
            return {"kind": drafted.kind.value, "version": drafted.version, "via": "tool"}
        if not output.strip():
            raise EmptyOutputError(NO_OUTPUT)
        doc = await write_draft(db, refs.board, refs.card, self.kind, output, run_id=self.run_id)
        return {"kind": doc.kind.value, "version": doc.version, "via": "reply"}

    async def record_success(self, db: AsyncSession, summary: dict[str, Any] | None) -> None:
        """Settle the run completed and tell the card's assignees."""
        self._revoke()
        self._completed = await apply.finish_succeeded(db, self.refs, summary or {})

    async def record_failure(self, db: AsyncSession, error: str) -> None:
        """Settle the run failed; the card stays as it was."""
        self._revoke()
        await apply.finish_failed(db, self.refs, error)

    async def record_cancel(self, reason: str) -> None:
        """Settle the run canceled on a fresh session, unless it already was."""
        self._revoke()
        await on_fresh_session(self.org_id, self.run_id, apply.finish_canceled, reason)

    async def record_crash(self, exc: Exception) -> None:
        """Settle the run failed on a fresh session (the main one was rolled back)."""
        self._revoke()
        await on_fresh_session(self.org_id, self.run_id, apply.finish_failed, str(exc))
        logger.exception("board_agent_run_failed", run_id=str(self.run_id))

    async def after_success(self) -> None:
        """Nothing more: the run's end was announced with its commit."""

    def announce(self) -> None:
        """Tell the Garden the agent finished (not when the run was canceled meanwhile)."""
        if self._completed:
            apply.garden_event(self.refs, "skill_completed")
