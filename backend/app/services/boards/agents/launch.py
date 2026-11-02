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

"""Starting a card run: the provider config, and marking the run running.

The CLI gets no built-in tools at all (``builtin_tools=[]``): no shell,
files or web, only the run's MCP tools. The run goes from ``pending`` to
``running`` with one conditional update, so a run canceled between loading
and starting (a move between boards, AI switched off) never starts.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.agent_skill import AgentSkill
from app.repositories.board_agent_run import BoardCardAgentRunRepository
from app.services.agents.subject import AgentRunCanceledError
from app.services.boards.agents.refs import RunRefs
from app.services.boards.agents.runs import queue_run_event, stop_reason
from app.services.claude_runner import ClaudeRunnerConfig, MCPServerConfig


def runner_config(
    skill: AgentSkill, timeout_seconds: int, mcp: MCPServerConfig | None
) -> ClaudeRunnerConfig:
    """How the provider runs the skill: its turns, deadline, model and the run's MCP only."""
    return ClaudeRunnerConfig(
        max_turns=skill.max_turns or settings.boards.agent_max_turns,
        timeout_seconds=timeout_seconds,
        mcp=mcp,
        model=skill.model or None,
        effort=skill.effort or None,
        # No shell, files or web: only the run's MCP tools.
        builtin_tools=[],
    )


async def mark_started(db: AsyncSession, refs: RunRefs) -> None:
    """Move the run to running, announce it on its board and commit.

    Raises:
        AgentRunCanceledError: The run isn't pending any more.
    """
    run = refs.run
    if not await BoardCardAgentRunRepository(db, org_id=run.org_id).mark_running(run):
        raise AgentRunCanceledError(stop_reason(run))
    await queue_run_event(db, refs.board.id, run)
    await db.commit()
