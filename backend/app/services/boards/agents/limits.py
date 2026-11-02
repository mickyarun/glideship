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

"""How many card runs may be going at once: per org and per person.

Pending and running runs count. Over either cap, the Run button answers 429
``AGENT_RUN_LIMIT`` (with ``Retry-After``) and no run is written. A card
entering an ``on_enter`` stage still records its run, failed at once with
the reason, so the card's AI panel shows why nothing ran and Retry can
start it later; the move itself goes ahead. The count is taken under the
org's run-start lock, held until the start commits, so two starts racing at
the edge of a cap can't both pass.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.repositories.board_agent_run import BoardCardAgentRunRepository

ORG_LIMIT = "Too many AI runs are going in your organization right now. Try again soon."
USER_LIMIT = "You have too many AI runs going right now. Try again when one finishes."


async def run_limit_reached(
    db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID | None
) -> str | None:
    """Why another run can't start now, or None when it can.

    Takes the org's run-start lock first (held until the caller commits),
    so call it with the card already locked and claim the run right after.
    """
    runs = BoardCardAgentRunRepository(db, org_id=org_id)
    await runs.lock_starts()
    if await runs.count_active() >= settings.boards.agent_runs_per_org_max:
        return ORG_LIMIT
    if user_id is not None and (
        await runs.count_active(triggered_by=user_id) >= settings.boards.agent_runs_per_user_max
    ):
        return USER_LIMIT
    return None
