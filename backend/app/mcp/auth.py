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

"""MCP token verification for Glideship tool calls from Claude Code.

:class:`MCPAuthResult` and the owner checks (:mod:`app.mcp.auth_result`,
:mod:`app.mcp.auth_owner`) are re-exported here.
"""

import asyncio
import secrets
import uuid
from typing import Any, NoReturn

import structlog
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, member_has_permission
from app.core.permissions import WORKSPACE_ENGINEERING
from app.core.security import hash_password, verify_password
from app.database import AsyncSessionLocal
from app.mcp.auth_owner import is_expired
from app.mcp.auth_owner import token_owner_still_allowed as token_owner_still_allowed
from app.mcp.auth_result import MCPAuthResult as MCPAuthResult
from app.mcp.auth_result import compute_token_prefix as compute_token_prefix
from app.mcp.token_grants import scoped_grant
from app.models.user_mcp_token import UserMCPToken
from app.repositories.organization import OrganizationRepository
from app.repositories.user import UserRepository
from app.repositories.user_mcp_token import UserMCPTokenRepository

logger = structlog.get_logger(__name__)

# Server-minted org-wide tokens (token → org_id) for internal CLI runs; they
# last until restart (eager revocation raced the shared token file).
_internal_tokens: dict[str, uuid.UUID] = {}
_MAX_INTERNAL_TOKENS = 100

# A throwaway bcrypt hash, computed once, checked on the no-match path so its
# timing can't reveal which token prefixes exist.
_TIMING_EQUALIZER_HASH = hash_password("bodhiorchard-timing-equalizer-not-a-real-token")

# In-flight last-used touches, held so they aren't garbage-collected.
_last_used_tasks: set[asyncio.Task[None]] = set()


def create_internal_mcp_token(org_id: uuid.UUID) -> str:
    """Create a temporary MCP token for internal use (e.g. scan pipeline).

    Valid until restart; past ``_MAX_INTERNAL_TOKENS`` the oldest is evicted.
    """
    token = secrets.token_urlsafe(32)
    if len(_internal_tokens) >= _MAX_INTERNAL_TOKENS:
        oldest_key = next(iter(_internal_tokens))
        _internal_tokens.pop(oldest_key)
        logger.debug("internal_token_evicted", evicted_token=oldest_key[:8])
    _internal_tokens[token] = org_id
    return token


async def _touch_last_used(token_id: uuid.UUID, org_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Bump ``last_used_at`` on its own session; a failure is logged, never raised."""
    try:
        async with AsyncSessionLocal() as session:
            await UserMCPTokenRepository(session).touch_last_used(token_id)
            await session.commit()
    except Exception:
        logger.exception(
            "mcp_token_last_used_touch_failed",
            token_id=str(token_id),
            org_id=str(org_id),
            user_id=str(user_id),
        )


def _schedule_last_used(token_id: uuid.UUID, org_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Fire-and-forget last-used touch — never blocks the auth path."""
    task = asyncio.create_task(_touch_last_used(token_id, org_id, user_id))
    _last_used_tasks.add(task)
    task.add_done_callback(_last_used_tasks.discard)


def _refuse(
    event: str, ut: UserMCPToken, code: int, detail: str, *, level: str = "warning", **extra: Any
) -> NoReturn:
    """Log why a per-user token was refused, with its ids, and raise ``code``."""
    log = getattr(logger, level)
    log(event, token_id=str(ut.id), org_id=str(ut.org_id), user_id=str(ut.user_id), **extra)
    raise HTTPException(status_code=code, detail=detail)


async def verify_mcp_token(
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(),
) -> MCPAuthResult:
    """Verify the bearer token from an MCP request.

    In order: internal tokens (in-memory, server-minted; a scoped one, for a
    board card run, carries its grant and expires), per-user tokens (refused
    when expired or when the owner lost access; ``last_used_at`` bumped in
    the background), then org-level token hashes.

    Raises:
        HTTPException: If token is missing, invalid, or no match found.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
        )

    token = authorization[7:]

    logger.debug(
        "mcp_auth_attempt",
        token_prefix=token[:8] if len(token) >= 8 else token,
        internal_token_count=len(_internal_tokens),
    )

    org_repo = OrganizationRepository(db)

    # 1. Check internal tokens first (fast, in-memory). Org-wide ones never
    # expire and carry no grant; scoped ones (a board card run) carry theirs.
    internal_org_id = _internal_tokens.get(token)
    grant = None if internal_org_id is not None else scoped_grant(token)
    owner_id = internal_org_id or (grant.org_id if grant else None)
    if owner_id is not None:
        org = await org_repo.get_by_id(owner_id)
        if org:
            logger.debug("mcp_auth_internal", org_id=str(org.id))
            return MCPAuthResult(org=org, grant=grant)

    # 2. Per-user tokens: by prefix (indexed), then bcrypt (expired ones too,
    # so timing doesn't tell "missing" from "expired").
    prefix = compute_token_prefix(token)
    candidates = await UserMCPTokenRepository(db).list_by_prefix_with_relations(prefix)
    unauthorized = status.HTTP_401_UNAUTHORIZED
    for ut in candidates:
        if not verify_password(token, ut.token_hash):
            continue
        if is_expired(ut.expires_at):
            _refuse(
                "mcp_auth_user_token_expired", ut, unauthorized, "Token has expired", level="info"
            )
        # Defence-in-depth behind the revoke at deactivation (a soft delete),
        # and against a token whose user row is missing (a broken restore).
        if ut.user is None or not ut.user.is_active:
            _refuse(
                "mcp_auth_user_token_user_missing_or_inactive",
                ut,
                unauthorized,
                "Account is deactivated",
                user_loaded=ut.user is not None,
            )
        # A restore can keep users and tokens but lose their memberships.
        if not await UserRepository(db).is_member_of_org(ut.user_id, ut.org_id):
            _refuse(
                "mcp_auth_user_token_not_org_member",
                ut,
                unauthorized,
                "User is not a member of the token's organization",
            )
        # Checked on every call, so a move to a people-only role cuts it off.
        if not await member_has_permission(db, ut.user_id, ut.org_id, WORKSPACE_ENGINEERING):
            _refuse(
                "mcp_auth_user_token_no_engineering_access",
                ut,
                status.HTTP_403_FORBIDDEN,
                "Your role doesn't include engineering workspace access",
            )
        _schedule_last_used(ut.id, ut.org_id, ut.user_id)
        logger.debug(
            "mcp_auth_user_token",
            org_id=str(ut.org_id),
            user_id=str(ut.user_id),
            token_id=str(ut.id),
        )
        return MCPAuthResult(org=ut.organization, user=ut.user, token_id=ut.id)

    # 3. Fall back to org-level token hashes.
    for org in await org_repo.get_all_with_mcp_tokens():
        if org.mcp_token_hash and verify_password(token, org.mcp_token_hash):
            logger.debug("mcp_auth_success", org_id=str(org.id), slug=org.slug)
            return MCPAuthResult(org=org)

    # Equalize timing with the "prefix matched, bcrypt failed" path; a broken
    # bcrypt backend is logged rather than hidden behind the 401.
    if not candidates:
        try:
            verify_password(token, _TIMING_EQUALIZER_HASH)
        except ValueError:
            logger.warning("mcp_timing_equalizer_failed")

    raise HTTPException(status_code=unauthorized, detail="Invalid or expired MCP token")
