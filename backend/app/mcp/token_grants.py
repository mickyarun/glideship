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
may call, the one card and run its card tools may touch, and when it
expires; its run revokes it when it ends. Kept in memory, like internal
tokens.
"""

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

import structlog
from fastapi import HTTPException, status

logger = structlog.get_logger(__name__)

_MAX_SCOPED_TOKENS = 100


@dataclass(frozen=True)
class InternalTokenGrant:
    """What a server-minted token may do.

    The default grant is org-wide with every tool (the scan pipeline and BUD
    stage agents). A board card run narrows it: ``tools`` names the only
    tools the token may call, ``card_id`` the only card its card tools may
    touch (and only while ``run_id`` is still the card's active run), and
    ``expires_at`` ends it with the run.
    """

    org_id: uuid.UUID
    tools: frozenset[str] | None = None
    card_id: uuid.UUID | None = None
    run_id: uuid.UUID | None = None
    expires_at: datetime | None = None

    def allows(self, tool_name: str) -> bool:
        """Whether this grant may call ``tool_name``."""
        return self.tools is None or tool_name in self.tools


# Scoped tokens: token → grant.
_scoped_tokens: dict[str, InternalTokenGrant] = {}


class _HasGrant(Protocol):
    @property
    def grant(self) -> InternalTokenGrant | None: ...

    @property
    def org_id(self) -> uuid.UUID: ...


def _expired(expires_at: datetime | None) -> bool:
    return expires_at is not None and expires_at <= datetime.now(UTC)


def create_scoped_mcp_token(grant: InternalTokenGrant) -> str:
    """Mint an in-memory MCP token carrying ``grant`` (bounded, oldest dropped first).

    Returns:
        The plaintext token string.
    """
    token = secrets.token_urlsafe(32)
    if len(_scoped_tokens) >= _MAX_SCOPED_TOKENS:
        _scoped_tokens.pop(next(iter(_scoped_tokens)))
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


def require_tool_grant(auth: _HasGrant, tool_name: str) -> None:
    """Refuse a call the token's grant doesn't cover (403).

    Raises:
        HTTPException: The token is scoped and ``tool_name`` isn't in its grant.
    """
    if auth.grant is not None and not auth.grant.allows(tool_name):
        logger.warning("mcp_tool_outside_grant", tool=tool_name, org_id=str(auth.org_id))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This token may not call {tool_name}",
        )
