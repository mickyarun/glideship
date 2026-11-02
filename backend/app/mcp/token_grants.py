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

"""Scoped server-minted MCP tokens: what a board card run's token may do.

An org-wide internal token (scan pipeline, BUD agents) has no grant. A
scoped one carries an :class:`InternalTokenGrant` naming the only tools it
may call, the one card and run its card tools may touch, the repositories
its code tools may read, and when it expires; its run revokes it when it
ends. Kept in memory, like internal tokens. A live token is never evicted to
make room: when the store is full of live tokens a new one is refused.
"""

import secrets
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final, Protocol

import structlog
from fastapi import HTTPException, status

logger = structlog.get_logger(__name__)

# The code-graph tools; each reads one repository named by its ``repo_id``.
REPO_SCOPED_TOOLS: Final = frozenset(
    {
        "code_impact",
        "code_query",
        "code_context",
        "code_community",
        "code_god_nodes",
        "code_stats",
    }
)
REPO_ID_PARAM: Final = "repo_id"
OTHER_REPO = "This run may read code only in its board's linked repositories (see the prompt)."


class ScopedTokenLimitError(Exception):
    """The store already holds as many live scoped tokens as it may."""


@dataclass(frozen=True)
class GrantRepo:
    """A repository a scoped token's code tools may read."""

    id: uuid.UUID
    name: str


@dataclass(frozen=True)
class InternalTokenGrant:
    """What a server-minted token may do.

    The default grant is org-wide with every tool (the scan pipeline and BUD
    stage agents). A board card run narrows it: ``tools`` names the only
    tools the token may call, ``card_id`` the only card its card tools may
    touch (and only while ``run_id`` is still the card's active run),
    ``repos`` the only repositories its code tools may read (``None`` means
    no limit), and ``expires_at`` ends it with the run.
    """

    org_id: uuid.UUID
    tools: frozenset[str] | None = None
    card_id: uuid.UUID | None = None
    run_id: uuid.UUID | None = None
    expires_at: datetime | None = None
    repos: tuple[GrantRepo, ...] | None = None

    def allows(self, tool_name: str) -> bool:
        """Whether this grant may call ``tool_name`` at all."""
        return self.tools is None or tool_name in self.tools

    def refusal(self, tool_name: str, params: Mapping[str, Any] | None) -> str | None:
        """Why this grant refuses the call, or None when it may go ahead."""
        if not self.allows(tool_name):
            return f"This token may not call {tool_name}"
        if self.repos is not None and tool_name in REPO_SCOPED_TOOLS:
            asked = str((params or {}).get(REPO_ID_PARAM) or "")
            if asked not in {str(r.id) for r in self.repos}:
                return OTHER_REPO
        return None

    def audit_fields(self) -> dict[str, str]:
        """The run and card a scoped call belongs to, for its audit row."""
        fields: dict[str, str] = {}
        if self.run_id is not None:
            fields["grant_run_id"] = str(self.run_id)
        if self.card_id is not None:
            fields["grant_card_id"] = str(self.card_id)
        return fields


# Scoped tokens: token → grant.
_scoped_tokens: dict[str, InternalTokenGrant] = {}


class _HasGrant(Protocol):
    @property
    def grant(self) -> InternalTokenGrant | None: ...

    @property
    def org_id(self) -> uuid.UUID: ...


def _expired(expires_at: datetime | None) -> bool:
    return expires_at is not None and expires_at <= datetime.now(UTC)


def _drop_expired() -> None:
    for token in [t for t, g in _scoped_tokens.items() if _expired(g.expires_at)]:
        _scoped_tokens.pop(token, None)


def create_scoped_mcp_token(grant: InternalTokenGrant, *, limit: int) -> str:
    """Mint an in-memory MCP token carrying ``grant``.

    Expired tokens are dropped first; live ones are never evicted.

    Raises:
        ScopedTokenLimitError: ``limit`` live tokens are already out.
    """
    if len(_scoped_tokens) >= limit:
        _drop_expired()
    if len(_scoped_tokens) >= limit:
        logger.warning("mcp_scoped_token_limit", limit=limit)
        raise ScopedTokenLimitError("Too many agent runs are going right now.")
    token = secrets.token_urlsafe(32)
    _scoped_tokens[token] = grant
    return token


def revoke_scoped_mcp_token(token: str) -> None:
    """Forget a scoped token; later calls with it are refused."""
    _scoped_tokens.pop(token, None)


def scoped_grant(token: str) -> InternalTokenGrant | None:
    """The live grant behind a scoped token, or None (unknown, org-wide or expired)."""
    grant = _scoped_tokens.get(token)
    if grant is None:
        return None
    if _expired(grant.expires_at):
        _scoped_tokens.pop(token, None)
        return None
    return grant


def require_tool_grant(
    auth: _HasGrant, tool_name: str, params: Mapping[str, Any] | None = None
) -> None:
    """Refuse a call the token's grant doesn't cover (403).

    Raises:
        HTTPException: The token is scoped and refuses ``tool_name`` (or its repository).
    """
    reason = None if auth.grant is None else auth.grant.refusal(tool_name, params)
    if reason is not None:
        logger.warning("mcp_tool_outside_grant", tool=tool_name, org_id=str(auth.org_id))
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)


def require_unscoped(auth: _HasGrant) -> None:
    """Refuse a scoped token on routes that only org-wide or user tokens may use (403).

    Raises:
        HTTPException: The token carries a grant.
    """
    if auth.grant is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="This token may not use this route"
        )
