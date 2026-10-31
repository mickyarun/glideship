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

"""The BUD side of a handover, inside its transaction: create and land it, or link it.

Create goes through :func:`app.services.bud_create.create_bud` at ``bud``,
without starting that stage. Its first ``bud_versions`` row is written with
the handing-over person as editor, so BUD authorship (the earliest
version's editor) names them. A ``handed_over_from_board`` event follows
(stamped from the database clock, so it reads after ``created``), then
:func:`handover_landing.land` walks it to the target. A link leaves the BUD
as it is apart from that event; the confirm has already locked that BUD.
"""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_card import BoardCard
from app.models.bud import BUDDocument, BUDStatus, BUDTimelineEventType
from app.models.bud_version import BUDEditSource
from app.repositories import bud_version as bud_version_repo
from app.schemas.boards.handover import HandoverConfirm
from app.services.boards.access import BoardAccess
from app.services.boards.handover_landing import land
from app.services.boards.handover_prepare import prepare
from app.services.boards.handover_rules import linkable_bud
from app.services.boards.handover_similar import draft_embedding
from app.services.boards.reads import card_key
from app.services.bud_create import create_bud
from app.services.bud_timeline import clock_now, record_event

# The ``created`` event's source for a BUD made by handing a card over.
SOURCE_BOARD = "board"


@dataclass(frozen=True)
class HandedOverBUD:
    """The BUD a handover created or linked; ``previous`` is set only for a created one."""

    bud: BUDDocument
    previous: BUDStatus | None


def origin_detail(access: BoardAccess, card: BoardCard, **extra: Any) -> dict[str, Any]:
    """The ``handed_over_from_board`` event's detail: the board, the card and its key."""
    return {
        "board_id": str(access.board.id),
        "card_id": str(card.id),
        "card_key": card_key(access.board.key, card.number),
        **extra,
    }


async def create_and_land(
    db: AsyncSession,
    access: BoardAccess,
    card: BoardCard,
    body: HandoverConfirm,
    *,
    actor_name: str | None,
) -> HandedOverBUD:
    """Create the card's BUD at ``bud`` and land it at the target status.

    Raises:
        HandoverNeedsRequirementsError: A tech-plan landing with nothing to plan from.
        BoardRuleError: An overridden repository isn't one of the org's active ones.
    """
    prepared = await prepare(db, access, card, body)
    create, target = prepared.create, prepared.target
    bud = await create_bud(
        db,
        org_id=access.org_id,
        body=create,
        actor_id=access.user_id,
        actor_name=actor_name,
        source=SOURCE_BOARD,
        embedding=await draft_embedding(access.org_id, create.title, create.requirements_md),
        start_stage=False,
    )
    bud.impacted_repos = prepared.impacted_repos_json
    await bud_version_repo.insert_snapshot(
        db,
        bud=bud,
        phase=BUDStatus.BUD,
        source=BUDEditSource.UI,
        edited_by=access.user_id,
        reason=f"Handed over from {card_key(access.board.key, card.number)}",
    )
    await record_event(
        db,
        access.org_id,
        bud.id,
        BUDTimelineEventType.HANDED_OVER_FROM_BOARD.value,
        actor_id=access.user_id,
        actor_name=actor_name,
        detail=origin_detail(access, card, target_status=target.value),
        occurred_at=await clock_now(db, access.org_id),
    )
    previous = await land(
        db, access.org_id, bud, target, actor_id=access.user_id, actor_name=actor_name
    )
    return HandedOverBUD(bud=bud, previous=previous)


async def link(
    db: AsyncSession,
    access: BoardAccess,
    card: BoardCard,
    bud_id: uuid.UUID,
    *,
    actor_name: str | None,
) -> HandedOverBUD:
    """Make the card the BUD's origin; the BUD gets one timeline event and nothing else.

    The caller holds the BUD's lock, so the checks are final here.

    Raises:
        BoardItemNotFoundError / BUDNotOpenError / BUDAlreadyLinkedError /
            BUDHasOtherOriginError: As :func:`handover_rules.linkable_bud`.
    """
    bud = await linkable_bud(db, access, card, bud_id)
    await record_event(
        db,
        access.org_id,
        bud.id,
        BUDTimelineEventType.HANDED_OVER_FROM_BOARD.value,
        actor_id=access.user_id,
        actor_name=actor_name,
        detail=origin_detail(access, card, linked=True),
        occurred_at=await clock_now(db, access.org_id),
    )
    return HandedOverBUD(bud=bud, previous=None)
