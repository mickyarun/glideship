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

"""Sending a check-in: from then on the manager and HR read what it says.

Only the person sends their own, while it is open, once. Sending starts
the clock on the manager's note that answers it (:mod:`.note_clock`).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.appraisals.context import CheckInContext
from app.services.appraisals.errors import AppraisalConflictError
from app.services.appraisals.note_clock import start_on_send


async def send_check_in(db: AsyncSession, ctx: CheckInContext, actor_id: uuid.UUID) -> None:
    """Send the caller's own open check-in."""
    check_in = ctx.check_in
    if not (ctx.is_open and ctx.profile.user_id == actor_id):
        raise AppraisalConflictError("Only the person can send their open check-in.")
    if check_in.sent_at is not None:
        raise AppraisalConflictError("This check-in was already sent.")
    check_in.sent_at = datetime.now(UTC)
    await start_on_send(db, check_in)
    await db.flush()
