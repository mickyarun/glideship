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

"""What a BUD status change records and assigns, once the caller's guards pass.

The status PATCH and :func:`app.services.bud_discard.discard_bud` both call
:func:`apply_status_change`. It doesn't set ``bud.status`` (except on entry
to development, which the hook below needs), transition the linked feature
or start agents: the callers do, in the order they always have. A discard
re-checks the origin card's delivery (:func:`recheck_after_discard`).
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bud import BUDDocument, BUDStatus, BUDTimelineEventType
from app.services.boards.handover_live import queue_origin_card_refresh
from app.services.boards.notify import recheck_after_discard
from app.services.bud_assignment import auto_assign_for_phase
from app.services.bud_development import on_bud_development_started
from app.services.bud_timeline import record_event


async def apply_status_change(
    db: AsyncSession,
    org_id: uuid.UUID,
    bud: BUDDocument,
    old_status: BUDStatus,
    new_status: BUDStatus,
    *,
    actor_id: uuid.UUID,
    actor_name: str | None,
) -> None:
    """Record ``status_change``, assign the new phase's owner, start development."""
    await record_event(
        db,
        org_id,
        bud.id,
        BUDTimelineEventType.STATUS_CHANGE.value,
        actor_id=actor_id,
        actor_name=actor_name,
        detail={"from": old_status.value, "to": new_status.value},
    )
    entering_development = (
        old_status != BUDStatus.DEVELOPMENT and new_status == BUDStatus.DEVELOPMENT
    )
    # Applied before the side effects so the hooks and assignment policy
    # see the right phase.
    if entering_development:
        bud.status = new_status
    # Sets ``bud.assignee_id``; runs before the development hook so the
    # TODOs it syncs go to that lead in the same transaction.
    await auto_assign_for_phase(
        db, org_id, bud, new_status, actor_id=actor_id, actor_name=actor_name
    )
    # Same side effects as approving the tech plan: TODOs parsed from the
    # tech spec and assigned to the lead, PERT estimation scheduled.
    if entering_development:
        await on_bud_development_started(db, org_id, bud, actor_id=actor_id, actor_name=actor_name)
    # A discarded BUD no longer holds its card's delivery back.
    if new_status == BUDStatus.DISCARDED:
        await recheck_after_discard(db, org_id, bud, actor_id=actor_id)
    # Boards holding the BUD refresh its chip once this commits; logged, never raised.
    await queue_origin_card_refresh(db, org_id, bud.id)
