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

"""Land a handed-over BUD at its target status; after the commit, start that stage only.

:func:`land` runs in the handover's transaction. A new BUD starts at
``bud``; for each status it skips on the way (``bud → design``, then
``design → tech_arch``) it writes an ordinary ``status_change`` event with
the handing-over person as actor and ``detail.via = "handover"``, and moves
the linked feature as a status PATCH would. Each step is stamped from the
database clock (``clock_timestamp()``), so the steps read in order after
``created`` and the phase windows give the time to the target. ``sp_pm``
and ``sp_tech_arch`` read those events like any other, so the PM credit for
the requirements goes to the person who handed over. Then the target
stage's owner is assigned in the same transaction, and a BUD landing past
``bud`` gets the estimate a finished PRD would give it, once this commits.

:func:`start_target_agent` runs after the commit: only the agent for the
target stage. The skipped stages' agents don't run; the board already did
that work.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bud import BUDDocument, BUDStatus, BUDTimelineEventType
from app.services import bud_estimate_after_commit
from app.services.boards.constants import HANDOVER_LANDING_STATUSES, VIA_HANDOVER
from app.services.bud_assignment import auto_assign_for_phase
from app.services.bud_create import start_intake_agent
from app.services.bud_stage_jobs import StageJobsOutcome, run_stage_jobs
from app.services.bud_timeline import clock_now, record_event
from app.services.feature_lifecycle import transition_feature_for_bud

# The estimate's trigger, as its snapshot records it.
ESTIMATE_TRIGGER = "handover_landed"


async def land(
    db: AsyncSession,
    org_id: uuid.UUID,
    bud: BUDDocument,
    target: BUDStatus,
    *,
    actor_id: uuid.UUID,
    actor_name: str | None,
) -> BUDStatus:
    """Walk a new ``bud`` up to ``target``, assign its owner; the status before the last step."""
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
            occurred_at=await clock_now(db, org_id),
        )
        previous, bud.status = bud.status, status
    await db.flush()
    await auto_assign_for_phase(
        db, org_id, bud, bud.status, actor_id=actor_id, actor_name=actor_name
    )
    if steps:
        bud_estimate_after_commit.schedule(
            db,
            org_id=org_id,
            bud_id=bud.id,
            trigger=ESTIMATE_TRIGGER,
            actor_id=actor_id,
            actor_name=actor_name,
        )
    return previous


def previous_of(status: BUDStatus) -> BUDStatus:
    """The status a landing at ``status`` stepped from (``bud`` for itself)."""
    index = HANDOVER_LANDING_STATUSES.index(status)
    return HANDOVER_LANDING_STATUSES[max(index - 1, 0)]


async def start_target_agent(
    db: AsyncSession,
    org_id: uuid.UUID,
    bud: BUDDocument,
    previous: BUDStatus,
    *,
    triggered_by: uuid.UUID,
) -> StageJobsOutcome:
    """Start the agent for the status the BUD landed at; the owner is already assigned.

    At ``bud`` this is the PM agent creating a BUD starts; further on it is
    what a status PATCH into that status starts. May commit (the agent call does).
    """
    if bud.status is BUDStatus.BUD:
        await start_intake_agent(db, org_id, bud, triggered_by=triggered_by)
        return StageJobsOutcome()
    return await run_stage_jobs(db, org_id, bud, previous, bud.status, triggered_by=triggered_by)
