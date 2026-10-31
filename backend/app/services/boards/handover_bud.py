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
version's editor) names them. A ``handed_over_from_board`` event follows,
then :func:`handover_landing.land` walks it to the target. A link leaves
the BUD as it is apart from that event.
"""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_card import BoardCard
from app.models.bud import BUDDocument, BUDStatus, BUDTimelineEventType
from app.models.bud_version import BUDEditSource
from app.repositories import bud_version as bud_version_repo
from app.repositories.board_repo import BoardRepoRepository
from app.repositories.bud import BUDRepository
from app.schemas.boards.handover import HandoverConfirm, HandoverOverrides, ImpactedRepo
from app.schemas.bud import BUDCreate
from app.services.boards.access import BoardAccess
from app.services.boards.errors import BoardItemNotFoundError, BoardRuleError
from app.services.boards.handover_content import draft_for, impacted
from app.services.boards.handover_landing import land
from app.services.boards.handover_rules import (
    BUD_NOT_FOUND,
    check_requirements,
    linkable_bud,
    target_of,
)
from app.services.boards.handover_similar import draft_embedding
from app.services.boards.reads import card_key
from app.services.bud_create import create_bud
from app.services.bud_timeline import record_event

# The ``created`` event's source for a BUD made by handing a card over.
SOURCE_BOARD = "board"
UNKNOWN_REPOS = "Pick repositories from the organisation's active ones."


@dataclass(frozen=True)
class HandedOverBUD:
    """The BUD a handover created or linked; ``previous`` is set only for a created one."""

    bud: BUDDocument
    previous: BUDStatus | None


def _origin(access: BoardAccess, card: BoardCard, **extra: Any) -> dict[str, Any]:
    return {
        "board_id": str(access.board.id),
        "card_id": str(card.id),
        "card_key": card_key(access.board.key, card.number),
        **extra,
    }


async def _repos(
    db: AsyncSession, access: BoardAccess, drafted: list[ImpactedRepo], o: HandoverOverrides
) -> list[ImpactedRepo]:
    if o.impacted_repo_ids is None:
        return drafted
    wanted = list(dict.fromkeys(o.impacted_repo_ids))
    found = await BoardRepoRepository(db, org_id=access.org_id).active_among(wanted)
    if len(found) != len(wanted):
        raise BoardRuleError(UNKNOWN_REPOS)
    return impacted(found)


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
    draft = await draft_for(db, access, card)
    o = body.overrides or HandoverOverrides()
    title = o.title or draft.title
    requirements = draft.requirements_md if o.requirements_md is None else o.requirements_md
    target = target_of(access, body)
    check_requirements(target, draft.source_md if o.requirements_md is None else requirements)
    repos = await _repos(db, access, draft.impacted_repos, o)
    create = BUDCreate(
        title=title,
        requirements_md=requirements or None,
        priority=draft.priority,
        figma_url=draft.figma_url,
        auto_generate_phases={s.value: on for s, on in body.auto_generate_phases.items()},
    )
    bud = await create_bud(
        db,
        org_id=access.org_id,
        body=create,
        actor_id=access.user_id,
        actor_name=actor_name,
        source=SOURCE_BOARD,
        embedding=await draft_embedding(access.org_id, title, create.requirements_md),
        start_stage=False,
    )
    bud.impacted_repos = [repo.model_dump(mode="json") for repo in repos] or None
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
        detail=_origin(access, card, target_status=target.value),
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

    Raises:
        BoardItemNotFoundError / BUDNotOpenError / BUDAlreadyLinkedError /
            BUDHasOtherOriginError: As :func:`handover_rules.linkable_bud`.
    """
    if not await BUDRepository(db, org_id=access.org_id).lock_for_edit(bud_id):
        raise BoardItemNotFoundError(BUD_NOT_FOUND)
    bud = await linkable_bud(db, access, card, bud_id)
    await record_event(
        db,
        access.org_id,
        bud.id,
        BUDTimelineEventType.HANDED_OVER_FROM_BOARD.value,
        actor_id=access.user_id,
        actor_name=actor_name,
        detail=_origin(access, card, linked=True),
    )
    return HandedOverBUD(bud=bud, previous=None)
