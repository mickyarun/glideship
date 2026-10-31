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

"""Who an MCP call is authenticated as, and the non-secret token prefix used to find it."""

import hashlib
import uuid
from dataclasses import dataclass, field

from app.mcp.token_grants import InternalTokenGrant
from app.models.organization import Organization
from app.models.user import User


def compute_token_prefix(plaintext_token: str) -> str:
    """Compute a non-secret prefix for indexed token lookup.

    Uses SHA-256 of the plaintext, truncated to 16 hex chars. This is NOT a
    secret: it's stored in plaintext for fast filtering before the expensive
    bcrypt verification.
    """
    return hashlib.sha256(plaintext_token.encode()).hexdigest()[:16]


@dataclass(frozen=True)
class MCPAuthResult:
    """Result of MCP token verification.

    Always contains an org. Contains a user when the token is
    a per-user token (UserMCPToken), None for org-level or internal tokens.
    ``token_id`` is the UserMCPToken row id when the call was authenticated
    by a per-user token — used by the audit log so an admin can trace any
    recorded action back to a specific revocable credential.
    """

    org: Organization
    user: User | None = None
    token_id: uuid.UUID | None = None
    # Set for a scoped server-minted token; it limits tools and cards.
    grant: InternalTokenGrant | None = None
    # Plain copies of the ORM ids, taken while the request session is
    # healthy. A handler whose flush fails rolls the session back and
    # expires ``org`` and ``user``; reading ``org.id`` after that raises,
    # so the audit write on the error path must use these instead.
    org_id: uuid.UUID = field(init=False)
    user_id: uuid.UUID | None = field(init=False)

    def __post_init__(self) -> None:
        """Snapshot the org and user ids at authentication time."""
        object.__setattr__(self, "org_id", self.org.id)
        object.__setattr__(self, "user_id", self.user.id if self.user else None)
