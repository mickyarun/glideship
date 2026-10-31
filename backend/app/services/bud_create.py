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

"""Create a BUD the way ``POST /buds`` does: one path for every caller.

:func:`create_bud` numbers the BUD, stores its stage skill picks, embeds it
(or takes an embedding the caller already made), plans its feature and
records ``created``. Unless the caller asks it not to, it then starts the
``bud`` stage (:func:`start_intake`): auto-assignment and, when the phase is
switched on, the PM agent. A handover lands the BUD further on, so it skips
that and starts its target stage itself.
"""

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bud import BUDDocument, BUDStatus, BUDTimelineEventType
from app.repositories.bud import BUDRepository
from app.schemas.bud import BUDCreate
from app.services.bud_agent_trigger import create_agent_task_for_stage, should_auto_generate_phase
from app.services.bud_assignment import auto_assign_for_phase
from app.services.bud_stage_overrides import persist_stage_skill_overrides
from app.services.bud_timeline import record_event
from app.services.embedding_service import embedding_service
from app.services.feature_lifecycle import create_planned_feature

logger = structlog.get_logger(__name__)

# How much of the requirements goes into the embedded text after the title.
EMBED_REQUIREMENTS_CHARS = 500


def embed_text_for(title: str, requirements_md: str | None) -> str:
    """The text a new BUD's embedding is made from."""
    if requirements_md:
        return f"{title} {requirements_md[:EMBED_REQUIREMENTS_CHARS]}"
    return title


async def create_bud(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    body: BUDCreate,
    actor_id: uuid.UUID,
    actor_name: str | None,
    source: str = "web",
    embedding: list[float] | None = None,
    start_stage: bool = True,
) -> BUDDocument:
    """Create a BUD at ``bud`` with the next number in the org.

    ``embedding`` is used as it is when given (it must be made from
    :func:`embed_text_for`); otherwise the text is embedded here, and a
    failure only logs, as the bug linker can live without it.

    Raises:
        StageSkillOverrideError: A stage skill pick doesn't fit its stage.
    """
    bud_repo = BUDRepository(db, org_id=org_id)
    next_number = await bud_repo.next_bud_number()

    # Empty dict from the schema default = all phases skip. Stored as
    # the JSONB literal (not NULL) so the frontend can distinguish a
    # freshly-created opt-out from a never-explicitly-set legacy row.
    bud = BUDDocument(
        org_id=org_id,
        bud_number=next_number,
        title=body.title,
        status=BUDStatus.BUD,
        priority=body.priority,
        requirements_md=body.requirements_md,
        figma_url=body.figma_url,
        metadata_=body.metadata_,
        auto_generate_phases=body.auto_generate_phases,
    )
    await bud_repo.create(bud)

    # Per-BUD stage skill picks (Advanced settings on create), stored before
    # any agent is asked so the first run already uses them.
    if body.stage_skill_overrides:
        await persist_stage_skill_overrides(db, org_id, bud.id, body.stage_skill_overrides)

    # Embedded inline (~50ms) so the bug linker can match bugs right away.
    try:
        if embedding is None:
            embedding = await embedding_service.embed(
                embed_text_for(body.title, body.requirements_md)
            )
        bud.embedding = embedding
        await db.flush()
    except Exception:
        logger.warning("bud_embedding_failed", bud_number=next_number, exc_info=True)

    await create_planned_feature(db, org_id, next_number, body.title, body.requirements_md or "")
    await record_event(
        db,
        org_id,
        bud.id,
        BUDTimelineEventType.CREATED.value,
        actor_id=actor_id,
        actor_name=actor_name,
        detail={"source": source},
    )
    logger.info(
        "bud_created",
        bud_id=str(bud.id),
        bud_number=next_number,
        org_id=str(bud.org_id),
        auto_generate_phases=body.auto_generate_phases,
    )
    if start_stage:
        await start_intake(db, org_id, bud, actor_id=actor_id, actor_name=actor_name)
    # Estimation is deferred: it runs after the PRD agent completes.
    return bud


async def start_intake(
    db: AsyncSession,
    org_id: uuid.UUID,
    bud: BUDDocument,
    *,
    actor_id: uuid.UUID,
    actor_name: str | None,
) -> None:
    """Start the ``bud`` stage: assign its owner, then the PM agent if switched on.

    External-LLM mode: each phase is opt-in, so the agent only runs when
    the BUD's ``bud`` phase is enabled; otherwise the user supplies the PRD.
    The agent call commits the session.
    """
    await auto_assign_for_phase(
        db, org_id, bud, BUDStatus.BUD, actor_id=actor_id, actor_name=actor_name
    )
    await start_intake_agent(db, org_id, bud, triggered_by=actor_id)


async def start_intake_agent(
    db: AsyncSession, org_id: uuid.UUID, bud: BUDDocument, *, triggered_by: uuid.UUID
) -> None:
    """Ask for the PM agent when the BUD's ``bud`` phase is on; that call commits."""
    if should_auto_generate_phase(bud.auto_generate_phases, BUDStatus.BUD.value):
        await create_agent_task_for_stage(
            bud, BUDStatus.BUD.value, org_id, db, triggered_by=triggered_by, force=True
        )
