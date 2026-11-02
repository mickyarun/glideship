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

"""Estimate a BUD's phase dates in the background, once the caller's change commits.

The PERT estimator is an LLM call (~10-30s), so it runs as an asyncio task
with its own DB session. Spawning it before the commit would race it: the
new session could read the BUD as it was. :func:`schedule` queues the
spawn with :func:`app.services.after_commit.call_after_commit`: it runs
when the outermost transaction commits (not at a SAVEPOINT), and a
rollback drops it. Failures are
logged and shown in the activity feed, never raised.
"""

import asyncio
import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.bud import BUDDocument
from app.repositories.bud import BUDRepository
from app.services.after_commit import call_after_commit
from app.services.agent_activity_logger import log_agent_activity
from app.services.bud_estimation import estimate_bud_dates

logger = structlog.get_logger(__name__)

# Hold strong refs to in-flight PERT background tasks so the GC doesn't
# eat them mid-await; tasks remove themselves on completion. Same pattern
# documented in CLAUDE.md and used by github_app_slug._BACKGROUND_RETROFIT_TASKS.
_BACKGROUND_ESTIMATION_TASKS: set[asyncio.Task[None]] = set()

_ESTIMATOR_SLUG = "pert_estimator"


def schedule(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    bud_id: uuid.UUID,
    trigger: str,
    actor_id: uuid.UUID | None,
    actor_name: str | None,
) -> None:
    """Defer the PERT estimator task to fire after the caller's commit.

    Queued to run once the outermost transaction commits, so the new DB
    session the task opens reads post-transition state (new status, lead
    assignee, freshly-inserted TODOs). Without this
    deferral the task races the caller's commit and may estimate on
    stale data. Estimation is non-fatal — failures are logged and
    surfaced to the activity log, never raised.
    """

    def _on_commit() -> None:
        task = asyncio.create_task(
            _run_estimation(
                org_id=org_id,
                bud_id=bud_id,
                trigger=trigger,
                actor_id=actor_id,
                actor_name=actor_name,
            ),
            name=f"bg_estimate_bud_{bud_id}",
        )
        _BACKGROUND_ESTIMATION_TASKS.add(task)
        task.add_done_callback(_BACKGROUND_ESTIMATION_TASKS.discard)

    call_after_commit(db, _on_commit)


async def _run_estimation(
    *,
    org_id: uuid.UUID,
    bud_id: uuid.UUID,
    trigger: str,
    actor_id: uuid.UUID | None,
    actor_name: str | None,
) -> None:
    """Background task: re-estimate phase dates with a fresh DB session.

    Loads its own copy of the BUD because the caller's session is closed
    by the time this runs (intentional — we returned the request).
    """
    async with AsyncSessionLocal() as db:
        bud = await BUDRepository(db, org_id=org_id).get_by_id(bud_id)
        if bud is None:
            logger.warning("estimation_skipped_bud_missing", bud_id=str(bud_id))
            return

        await _emit_invoked(org_id, bud, "Re-estimating phase dates…")
        try:
            await estimate_bud_dates(
                db,
                org_id,
                bud,
                trigger=trigger,
                actor_id=actor_id,
                actor_name=actor_name,
            )
            await db.commit()
            await _emit_completed(org_id, bud, "Phase dates updated")
        except Exception as exc:
            await db.rollback()
            logger.warning(
                "estimation_failed_in_background",
                bud_id=str(bud.id),
                error=str(exc),
            )
            await log_agent_activity(
                None,
                org_id=org_id,
                event_type="skill_failed",
                skill_slug=_ESTIMATOR_SLUG,
                message=f"Estimation failed: {exc}",
                bud_id=bud.id,
                bud_number=bud.bud_number,
                bud_title=bud.title,
                metadata_={"error": str(exc)},
            )


async def _emit_invoked(org_id: uuid.UUID, bud: BUDDocument, message: str) -> None:
    """Publish a ``skill_invoked`` lifecycle event for the activity banner."""
    await log_agent_activity(
        None,
        org_id=org_id,
        event_type="skill_invoked",
        skill_slug=_ESTIMATOR_SLUG,
        message=message,
        bud_id=bud.id,
        bud_number=bud.bud_number,
        bud_title=bud.title,
    )


async def _emit_completed(org_id: uuid.UUID, bud: BUDDocument, message: str) -> None:
    """Publish a ``skill_completed`` lifecycle event for the activity banner."""
    await log_agent_activity(
        None,
        org_id=org_id,
        event_type="skill_completed",
        skill_slug=_ESTIMATOR_SLUG,
        message=message,
        bud_id=bud.id,
        bud_number=bud.bud_number,
        bud_title=bud.title,
    )
