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

"""Start a handed-over BUD's target stage after the commit, and retry it when that failed.

The confirm's transaction has already landed the BUD and assigned its
owner, so a failure here strands nothing but the agent run. It is logged,
and the handover row gets ``stage_start_failed_at``; the same confirm sent
again (its key) or ``POST .../handovers/{id}/retry-start`` runs the start
again and clears the mark once it succeeds.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_enums import BoardHandoverStatus
from app.models.bud import BUDDocument, BUDStatus
from app.repositories.board_handover import BoardHandoverRepository, HandoverRow
from app.repositories.bud import BUDRepository
from app.services.boards.handover_errors import HandoverStageStartedError
from app.services.boards.handover_landing import previous_of, start_target_agent

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class StageStart:
    """How a stage start went: the design hint for the client, or that it failed."""

    design_available: bool = False
    failed: bool = False


async def start_stage(
    db: AsyncSession,
    org_id: uuid.UUID,
    handover_id: uuid.UUID,
    bud: BUDDocument,
    previous: BUDStatus,
    *,
    actor_id: uuid.UUID,
) -> StageStart:
    """Ask for the target stage's agent; mark the handover when that fails. Commits.

    A failure rolls the session back, which expires everything it holds;
    the caller reloads what it still reads.
    """
    handovers = BoardHandoverRepository(db, org_id=org_id)
    bud_id = bud.id
    try:
        outcome = await start_target_agent(db, org_id, bud, previous, triggered_by=actor_id)
        await handovers.set_stage_start_failed(handover_id, None)
        await db.commit()
    except Exception:
        logger.exception("handover_stage_start_failed", bud_id=str(bud_id))
        await db.rollback()
        try:
            await handovers.set_stage_start_failed(handover_id, datetime.now(UTC))
            await db.commit()
        except Exception:
            logger.exception("handover_stage_start_mark_failed", bud_id=str(bud_id))
            await db.rollback()
        return StageStart(failed=True)
    return StageStart(design_available=outcome.design_available)


async def restart_failed(
    db: AsyncSession, org_id: uuid.UUID, row: HandoverRow, *, actor_id: uuid.UUID
) -> StageStart | None:
    """Start the stage again when it failed and the BUD still sits where it landed.

    None when there is nothing to retry. Commits the caller's transaction first.
    """
    handover, _ = row
    handover_id = handover.id
    if (
        handover.stage_start_failed_at is None
        or handover.status is not BoardHandoverStatus.ACTIVE
        or handover.bud_id is None
        or handover.target_status is None
    ):
        return None
    bud = await BUDRepository(db, org_id=org_id).get_by_id(handover.bud_id)
    if bud is None or bud.status is not handover.target_status:
        return None
    await db.commit()
    previous = previous_of(bud.status)
    return await start_stage(db, org_id, handover_id, bud, previous, actor_id=actor_id)


async def retry(
    db: AsyncSession, org_id: uuid.UUID, row: HandoverRow, *, actor_id: uuid.UUID
) -> StageStart:
    """:func:`restart_failed`, refusing a handover with nothing to retry.

    Raises:
        HandoverStageStartedError: The stage started, or the BUD has moved on.
    """
    started = await restart_failed(db, org_id, row, actor_id=actor_id)
    if started is None:
        raise HandoverStageStartedError()
    return started
