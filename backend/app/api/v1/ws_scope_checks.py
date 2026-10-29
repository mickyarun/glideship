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

"""Per-scope ownership checks a WebSocket subscription must pass.

:func:`app.services.ws_topic_policy.may_subscribe` answers from the topic
string alone. Every scope registers a check here, even when the string
check is all it needs, and a scope without one is refused.
"""

import uuid
from collections.abc import Awaitable, Callable

from app.database import AsyncSessionLocal
from app.repositories.board_access import BoardAccessRepository
from app.repositories.bud import BUDRepository
from app.services.ws_topic_policy import Scope, Subscriber, board_id_of, bud_id_of, scope_of

ScopeCheck = Callable[[str, Subscriber], Awaitable[bool]]


async def _owns_topic_bud(topic: str, who: Subscriber) -> bool:
    """For BUD-scoped topics, confirm the BUD belongs to the caller's org."""
    raw = bud_id_of(topic)
    if raw is None:
        return True
    try:
        bud_id = uuid.UUID(raw)
    except ValueError:
        return False
    async with AsyncSessionLocal() as db:
        return await BUDRepository(db, org_id=uuid.UUID(who.org_id)).exists(bud_id)


async def _has_board_role(topic: str, who: Subscriber) -> bool:
    """For board topics, confirm the caller holds a role on the board."""
    raw = board_id_of(topic)
    if raw is None:
        return False
    try:
        board_id = uuid.UUID(raw)
    except ValueError:
        return False
    async with AsyncSessionLocal() as db:
        repo = BoardAccessRepository(db, org_id=uuid.UUID(who.org_id))
        return await repo.role_for(board_id, uuid.UUID(who.user_id), who) is not None


async def _string_check_only(topic: str, who: Subscriber) -> bool:
    """``may_subscribe`` already matched the owner segment (or the id is the capability)."""
    return True


SCOPE_CHECKS: dict[Scope, ScopeCheck] = {
    "user": _string_check_only,
    "org": _string_check_only,
    "id": _string_check_only,
    "bud": _owns_topic_bud,
    "board": _has_board_role,
}


async def passes_scope_check(topic: str, who: Subscriber) -> bool:
    """Run the topic's scope check; an unknown or unregistered scope is refused."""
    scope = scope_of(topic)
    check = SCOPE_CHECKS.get(scope) if scope is not None else None
    return False if check is None else await check(topic, who)
