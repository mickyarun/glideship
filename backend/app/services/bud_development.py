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

"""Side effects when a BUD enters the DEVELOPMENT phase.

The tech spec churns freely during planning (chat edits, agent re-runs,
manual editing). TODOs are derived state that crystallizes once, when the
approved plan is locked in by the dev-phase transition. Mirrors the
``on_bud_closed`` pattern in ``bud_closure.py``.

TODO sync is now a deterministic parse over ``bud.tech_spec_md`` — it
runs in the request transaction and completes in milliseconds. PERT
estimation is still an LLM call (~10–30s); it fires as a background
asyncio task with its own DB session so the PATCH that triggered the
transition returns immediately.
"""

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bud import BUDDocument
from app.services import bud_estimate_after_commit
from app.services.event_bus import publish
from app.services.todo_assignment import assign_todos_per_repo_team
from app.services.todo_sync import sync_todos_for_bud

logger = structlog.get_logger(__name__)

# The estimate's trigger, as its snapshot records it.
DEVELOPMENT_STARTED_TRIGGER = "bud_development_started"


async def on_bud_development_started(
    db: AsyncSession,
    org_id: uuid.UUID,
    bud: BUDDocument,
    actor_id: uuid.UUID | None = None,
    actor_name: str | None = None,
) -> None:
    """Crystallize the dev-phase plan: sync TODOs, assign to lead, kick off PERT.

    Runs synchronously inside the caller's transaction for the cheap
    work (TODO sync + lead assignment). The PERT estimator — still an
    LLM call — fires as a background task with its own session.

    Caller ordering: this hook must run AFTER ``auto_assign_for_phase``
    so ``bud.assignee_id`` is set on the model when we assign TODOs to
    the lead.
    """
    try:
        count = await sync_todos_for_bud(db, org_id, bud, mode="initial")
    except Exception as exc:
        # Surface the failure to the user via the activity feed AND raise
        # so the caller's whole transition (status change, auto-assign,
        # timeline events) unwinds together — half-applied state was the
        # silent-data-loss footgun a previous version of this hook hid by
        # catching + rolling back here. The caller's commit must own the
        # all-or-nothing decision.
        logger.warning(
            "todo_sync_failed_on_dev_start",
            bud_id=str(bud.id),
            error=str(exc),
        )
        publish(
            f"todo:{bud.id}",
            {"event": "generating_failed", "error": str(exc)},
        )
        raise

    if bud.assignee_id is not None:
        await assign_todos_per_repo_team(db, org_id, bud.id, bud.assignee_id)

    publish(
        f"todo:{bud.id}",
        {
            "event": "todos_regenerated",
            "bud_id": str(bud.id),
            "todo_count": count,
        },
    )

    # PERT runs on a fresh DB session; spawning right now would race the
    # caller's commit (the new session could read pre-transition state).
    # Defer the spawn until after the caller's transaction commits.
    bud_estimate_after_commit.schedule(
        db,
        org_id=org_id,
        bud_id=bud.id,
        trigger=DEVELOPMENT_STARTED_TRIGGER,
        actor_id=actor_id,
        actor_name=actor_name,
    )
