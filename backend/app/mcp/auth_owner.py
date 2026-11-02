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

"""Checks on a per-user MCP token's owner and expiry, shared by calls and open streams."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import member_has_permission
from app.core.permissions import WORKSPACE_ENGINEERING
from app.repositories.user import UserRepository


async def token_owner_still_allowed(
    db: AsyncSession, user_id: uuid.UUID, org_id: uuid.UUID
) -> bool:
    """Whether a per-user token's owner may still use MCP.

    The owner must be active, a member of the token's org, and hold
    engineering access — the checks :func:`app.mcp.auth.verify_mcp_token`
    makes on every call. Long-lived streams re-run them on each heartbeat, so
    deactivating, removing or re-roling the owner cuts an open stream too,
    even when the token row itself survived.
    """
    user = await UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        return False
    if not await UserRepository(db).is_member_of_org(user_id, org_id):
        return False
    return await member_has_permission(db, user_id, org_id, WORKSPACE_ENGINEERING)


def is_expired(expires_at: datetime | None) -> bool:
    """True if a token has an expiry that's already in the past."""
    if expires_at is None:
        return False
    return expires_at <= datetime.now(UTC)
