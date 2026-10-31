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

"""What a card run may reach: the person behind it, its repositories, and its token.

The run's MCP token covers one card and one run, the tools
:func:`~app.services.boards.agents.tools.run_tools` picks, and (for the code
tools) only the board's active linked repositories. It expires with the
run's deadline plus a grace period and is revoked when the run ends. The
store of live tokens is bounded; a run that can't get one fails rather than
evicting another run's token.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.permission_deps import member_has_permission
from app.core.permissions import WORKSPACE_ENGINEERING
from app.mcp.token_grants import GrantRepo, InternalTokenGrant, create_scoped_mcp_token
from app.repositories.board_repo import BoardRepoRepository
from app.services.boards.agents.apply import RunRefs
from app.services.boards.agents.tools import BOARD_RUN_CODE_TOOLS, run_tools
from app.services.claude_runner import MCPServerConfig


@dataclass(frozen=True)
class RunReach:
    """Who the run acts for and what it may read: decided once, when the run loads."""

    engineering: bool
    repos: tuple[GrantRepo, ...]
    tools: frozenset[str]

    @property
    def code_tools(self) -> bool:
        """Whether the run may read code (the prompt then lists repository ids)."""
        return bool(self.tools & BOARD_RUN_CODE_TOOLS)


async def _engineering(db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID | None) -> bool:
    if user_id is None:
        return False
    return await member_has_permission(db, user_id, org_id, WORKSPACE_ENGINEERING)


async def run_reach(db: AsyncSession, refs: RunRefs) -> RunReach:
    """The run's reach, from the person who started it and the board's linked repositories."""
    org_id = refs.card.org_id
    engineering = await _engineering(db, org_id, refs.run.triggered_by)
    linked = await BoardRepoRepository(db, org_id=org_id).list_linked(refs.board.id)
    repos = tuple(GrantRepo(id=r.id, name=r.name) for r in linked)
    tools = run_tools(refs.skill.mcp_tools, engineering=engineering, has_repos=bool(repos))
    return RunReach(engineering=engineering, repos=repos, tools=tools)


def mint_run_token(
    refs: RunRefs, reach: RunReach, lifetime_seconds: int
) -> tuple[str, MCPServerConfig]:
    """A scoped token for the run, and the MCP config that carries it and its grant.

    Raises:
        ScopedTokenLimitError: Too many live run tokens already.
    """
    grant = InternalTokenGrant(
        org_id=refs.card.org_id,
        tools=reach.tools,
        card_id=refs.card.id,
        run_id=refs.run.id,
        expires_at=datetime.now(UTC) + timedelta(seconds=lifetime_seconds),
        repos=reach.repos,
    )
    token = create_scoped_mcp_token(grant, limit=settings.boards.agent_tokens_max)
    config = MCPServerConfig(
        backend_url=settings.mcp_backend_url,
        mcp_token=token,
        tool_names=sorted(reach.tools),
        org_id=str(refs.card.org_id),
        grant=grant,
    )
    return token, config
