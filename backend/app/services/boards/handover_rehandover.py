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

"""Hand a card over again after its BUD was sent back: the same BUD, restored.

A create-mode confirm on a card whose most recently returned handover still
points at a discarded BUD reuses that BUD, so its number isn't spent twice.
Inside the confirm's transaction (the BUD is already locked, then the card):

- the BUD is restored at ``bud`` through :func:`app.services.bud_restore.restore_bud`
  (``status_change`` tagged ``via: handover``, feature revived);
- the refreshed draft replaces its title, requirements, priority, Figma
  link, repositories, phase switches, stage skill picks (replaced, or
  cleared when none are given, as a new BUD starts with none) and
  embedding, and a new ``bud_versions`` row records it with the
  handing-over person as editor;
- ``handed_over_from_board`` (``again: true``), then
  :func:`handover_landing.land` walks it to the target as a new BUD's would.

The caller sets the same handover row back to ``active``; the card's events
keep the history.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_card import BoardCard
from app.models.board_enums import BoardHandoverStatus
from app.models.board_handover import BoardCardHandover
from app.models.bud import BUDStatus, BUDTimelineEventType
from app.models.bud_version import BUDEditSource
from app.repositories import bud_version as bud_version_repo
from app.repositories.bud import BUDRepository
from app.schemas.boards.handover import HandoverConfirm
from app.services.boards.access import BoardAccess
from app.services.boards.constants import VIA_HANDOVER
from app.services.boards.handover_bud import HandedOverBUD, origin_detail
from app.services.boards.handover_errors import BUDNotReturnedError
from app.services.boards.handover_landing import land
from app.services.boards.handover_prepare import prepare
from app.services.boards.handover_similar import draft_embedding
from app.services.boards.reads import card_key
from app.services.bud_restore import restore_bud
from app.services.bud_stage_overrides import persist_stage_skill_overrides
from app.services.bud_timeline import clock_now, record_event


async def hand_over_again(
    db: AsyncSession,
    access: BoardAccess,
    card: BoardCard,
    body: HandoverConfirm,
    row: BoardCardHandover,
    *,
    actor_name: str | None,
) -> HandedOverBUD:
    """Restore the returned BUD with the card's current draft and land it at the target.

    Raises:
        BUDNotReturnedError: The BUD was restored or deleted meanwhile.
        HandoverNeedsRequirementsError / BoardRuleError: As :func:`prepare`.
        StageSkillOverrideError: A stage skill pick doesn't fit its stage.
    """
    bud_id = row.bud_id
    bud = await BUDRepository(db, org_id=access.org_id).get_by_id(bud_id) if bud_id else None
    if bud is None or bud.status is not BUDStatus.DISCARDED:
        raise BUDNotReturnedError()
    prepared = await prepare(db, access, card, body)
    create = prepared.create
    await restore_bud(
        db,
        access.org_id,
        bud,
        actor_id=access.user_id,
        actor_name=actor_name,
        to_status=BUDStatus.BUD,
        detail={"via": VIA_HANDOVER},
    )
    bud.title = create.title
    bud.requirements_md = create.requirements_md
    bud.priority = create.priority
    bud.figma_url = create.figma_url
    bud.impacted_repos = prepared.impacted_repos_json
    bud.auto_generate_phases = create.auto_generate_phases
    bud.embedding = await draft_embedding(access.org_id, create.title, create.requirements_md)
    await persist_stage_skill_overrides(
        db, access.org_id, bud.id, create.stage_skill_overrides or {}
    )
    source = card_key(access.board.key, card.number)
    await bud_version_repo.insert_snapshot(
        db,
        bud=bud,
        phase=BUDStatus.BUD,
        source=BUDEditSource.UI,
        edited_by=access.user_id,
        reason=f"Handed over again from {source}",
    )
    await record_event(
        db,
        access.org_id,
        bud.id,
        BUDTimelineEventType.HANDED_OVER_FROM_BOARD.value,
        actor_id=access.user_id,
        actor_name=actor_name,
        detail=origin_detail(access, card, target_status=prepared.target.value, again=True),
        occurred_at=await clock_now(db, access.org_id),
    )
    previous = await land(
        db, access.org_id, bud, prepared.target, actor_id=access.user_id, actor_name=actor_name
    )
    return HandedOverBUD(bud=bud, previous=previous)


def reactivate(
    row: BoardCardHandover, actor_id: uuid.UUID, landed: BUDStatus, key: uuid.UUID
) -> BoardCardHandover:
    """Set the returned handover back to ``active`` for this confirm.

    The new ``idempotency_key`` is the row's current one (every key is also
    kept in ``board_card_handover_keys``); the return's facts are cleared
    from the row and stay in the card's events.
    """
    row.status = BoardHandoverStatus.ACTIVE
    row.target_status = landed
    row.handed_over_by = actor_id
    row.handed_over_at = datetime.now(UTC)
    row.returned_by = None
    row.returned_at = None
    row.return_reason = None
    row.stage_start_failed_at = None
    row.idempotency_key = key
    return row
