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

"""Land a handed-over BUD at its target status, then start that stage only.

:func:`land` runs in the handover's transaction. A new BUD starts at
``bud``; for each status it skips on the way (``bud → design``, then
``design → tech_arch``) it writes an ordinary ``status_change`` event with
the handing-over person as actor and ``detail.via = "handover"``, and moves
the linked feature as a status PATCH would. ``sp_pm`` and ``sp_tech_arch``
read those events like any other, so the PM credit for the requirements
goes to the person who handed over.

:func:`start_target_stage` runs after the commit: assignment and the agent
for the target stage. The skipped stages' agents don't run; the board
already did that work.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bud import BUDDocument, BUDStatus, BUDTimelineEventType
from app.services.boards.constants import HANDOVER_LANDING_STATUSES
from app.services.bud_assignment import auto_assign_for_phase
from app.services.bud_create import start_intake
from app.services.bud_stage_jobs import run_stage_jobs
from app.services.bud_timeline import record_event
from app.services.feature_lifecycle import transition_feature_for_bud

VIA_HANDOVER = "handover"


async def land(
    db: AsyncSession,
    org_id: uuid.UUID,
    bud: BUDDocument,
    target: BUDStatus,
    *,
    actor_id: uuid.UUID,
    actor_name: str | None,
) -> BUDStatus:
    """Walk a new ``bud`` up to ``target``; the status it was in before the last step."""
    steps = HANDOVER_LANDING_STATUSES[1 : HANDOVER_LANDING_STATUSES.index(target) + 1]
    previous = bud.status
    for status in steps:
        await transition_feature_for_bud(db, org_id, bud.bud_number, status)
        await record_event(
            db,
            org_id,
            bud.id,
            BUDTimelineEventType.STATUS_CHANGE.value,
            actor_id=actor_id,
            actor_name=actor_name,
            detail={"from": bud.status.value, "to": status.value, "via": VIA_HANDOVER},
        )
        previous, bud.status = bud.status, status
    await db.flush()
    return previous


async def start_target_stage(
    db: AsyncSession,
    org_id: uuid.UUID,
    bud: BUDDocument,
    previous: BUDStatus,
    *,
    actor_id: uuid.UUID,
    actor_name: str | None,
) -> None:
    """Assign the owner and start the agent for the status the BUD landed at.

    At ``bud`` this is what creating a BUD starts; further on it is what a
    status PATCH into that status starts. May commit (the agent call does).
    """
    if bud.status is BUDStatus.BUD:
        await start_intake(db, org_id, bud, actor_id=actor_id, actor_name=actor_name)
        return
    await auto_assign_for_phase(
        db, org_id, bud, bud.status, actor_id=actor_id, actor_name=actor_name
    )
    await run_stage_jobs(db, org_id, bud, previous, bud.status, triggered_by=actor_id)
