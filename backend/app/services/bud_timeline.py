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

"""Single entry point for recording BUD timeline events."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bud import BUDTimelineEvent
from app.repositories.bud_timeline import BUDTimelineRepository


async def record_event(
    db: AsyncSession,
    org_id: uuid.UUID,
    bud_id: uuid.UUID,
    event_type: str,
    actor_id: uuid.UUID | None = None,
    actor_name: str | None = None,
    detail: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> BUDTimelineEvent:
    """Append a timeline event to a BUD.

    ``created_at`` defaults to the transaction's start, so events written in
    one transaction tie. A caller writing steps that must read in order
    passes ``occurred_at`` from :func:`clock_now`.
    """
    repo = BUDTimelineRepository(db, org_id=org_id)
    event = BUDTimelineEvent(
        org_id=org_id,
        bud_id=bud_id,
        event_type=event_type,
        actor_id=actor_id,
        actor_name=actor_name,
        detail=detail,
    )
    if occurred_at is not None:
        event.created_at = occurred_at
    await repo.add(event)
    await repo.flush()
    return event


async def clock_now(db: AsyncSession, org_id: uuid.UUID) -> datetime:
    """The database's clock now; later on every call, even inside one transaction."""
    return await BUDTimelineRepository(db, org_id=org_id).clock_now()
