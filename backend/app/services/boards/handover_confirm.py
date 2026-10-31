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

"""Hand a card over to dev: one transaction, then the target stage and the owner's notice.

The transaction locks the card (:mod:`handover_card_stage`), returns the
first result for a repeated ``idempotency_key``, moves the card to the
handover stage on its first handover, creates and lands the BUD or links
one (:mod:`handover_bud`), inserts the ``board_card_handovers`` row and a
``handed_over`` card event, and queues the board's live events.

After it commits: assignment and the agent for the target stage
(:func:`handover_landing.start_target_stage`), then the owner's in-app row
and Slack DM. Those are logged, not raised, if they fail: the handover is
already saved, and a retry would only replay it.
"""

from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_enums import BoardCardEventType, BoardHandoverStatus
from app.models.board_handover import BoardCardHandover
from app.repositories.board_handover import BoardHandoverRepository, HandoverBUD
from app.repositories.user import UserRepository
from app.schemas.boards.handover import HandoverConfirm, HandoverMode, HandoverRead, HandoverResult
from app.services.boards.access import BoardAccess, CardAccess
from app.services.boards.card_notify import send
from app.services.boards.events import record_event
from app.services.boards.handover_bud import HandedOverBUD, create_and_land, link
from app.services.boards.handover_card_stage import CardStage, lock_card, move_on_first_handover
from app.services.boards.handover_landing import start_target_stage
from app.services.boards.handover_notify import stage_owner_notice
from app.services.boards.handover_reads import handover_read
from app.services.boards.handover_rules import check_allowed
from app.services.boards.handover_similar import bud_key
from app.services.boards.live import BoardChanges, BoardSocketEvent
from app.services.boards.reads import card_detail, summary_json

logger = structlog.get_logger(__name__)


async def confirm(db: AsyncSession, target: CardAccess, body: HandoverConfirm) -> HandoverResult:
    """Hand the card over as ``body`` says; the handover and the card as it now is.

    Raises:
        HandoverPermissionError / HandoverDisabledError: As ``check_allowed``.
        BoardConflictError: The card is archived, or changed while locking.
        StageRequirementsMissingError / ChecklistOpenError: The first
            handover can't move the card into the handover stage.
        HandoverNeedsRequirementsError, BUDNotOpenError, BUDAlreadyLinkedError,
            BUDHasOtherOriginError, BoardItemNotFoundError: From the BUD side.
    """
    access, card = target.access, target.card
    check_allowed(access, card, body.mode)
    locked = await lock_card(db, target)
    handovers = BoardHandoverRepository(db, org_id=access.org_id)
    replay = await handovers.by_idempotency_key(card.id, body.idempotency_key)
    if replay is not None:
        return HandoverResult(
            handover=handover_read(replay), card=await card_detail(db, access.board, card)
        )
    first = await handovers.count_for_card(card.id) == 0
    stage = await move_on_first_handover(
        db, target, locked, first=first, confirm_open_checklist=body.confirm_open_checklist
    )
    actor_name = await _actor_name(db, access)
    if body.mode is HandoverMode.LINK:
        assert body.bud_id is not None  # the schema requires it for a link
        result = await link(db, access, card, body.bud_id, actor_name=actor_name)
    else:
        result = await create_and_land(db, access, card, body, actor_name=actor_name)
    read = await _record(db, target, body, result, stage)
    detail = await card_detail(db, access.board, card)
    changes = BoardChanges.of(access)
    if stage.rebalanced and stage.to_stage is not None:
        changes.emit(BoardSocketEvent.STAGE_REORDERED, stage_id=str(stage.to_stage.id))
    if stage.moved:
        changes.emit(
            BoardSocketEvent.CARD_MOVED,
            card=summary_json(detail),
            from_stage_id=str(stage.from_stage.id),
        )
    changes.emit(
        BoardSocketEvent.CARD_HANDED_OVER,
        card_id=str(card.id),
        handover=read.model_dump(mode="json"),
    )
    await changes.commit(db)
    await _after_commit(db, target, result, actor_name)
    return HandoverResult(handover=read, card=detail)


async def _record(
    db: AsyncSession,
    target: CardAccess,
    body: HandoverConfirm,
    result: HandedOverBUD,
    stage: CardStage,
) -> HandoverRead:
    """Insert the handover row and the card's ``handed_over`` event."""
    access, card, bud = target.access, target.card, result.bud
    linked = body.mode is HandoverMode.LINK
    row = await BoardHandoverRepository(db, org_id=access.org_id).add(
        BoardCardHandover(
            org_id=access.org_id,
            card_id=card.id,
            bud_id=bud.id,
            status=BoardHandoverStatus.ACTIVE,
            linked_existing=linked,
            target_status=None if linked else bud.status,
            handed_over_by=access.user_id,
            handed_over_at=datetime.now(UTC),
            idempotency_key=body.idempotency_key,
        )
    )
    await record_event(
        db,
        card,
        BoardCardEventType.HANDED_OVER,
        actor_id=access.user_id,
        from_stage=stage.from_stage if stage.moved else None,
        to_stage=stage.to_stage,
        detail={
            "bud_id": str(bud.id),
            "bud_key": bud_key(bud.bud_number),
            "mode": body.mode.value,
            "bud_status": bud.status.value,
        },
    )
    return handover_read((row, HandoverBUD(bud.bud_number, bud.title, bud.status)))


async def _after_commit(
    db: AsyncSession, target: CardAccess, result: HandedOverBUD, actor_name: str | None
) -> None:
    """Start the target stage of a created BUD, then tell the BUD's owner."""
    access, bud = target.access, result.bud
    if result.previous is not None:
        try:
            await start_target_stage(
                db,
                access.org_id,
                bud,
                result.previous,
                actor_id=access.user_id,
                actor_name=actor_name,
            )
            await db.commit()
        except Exception:
            logger.exception("handover_stage_start_failed", bud_id=str(bud.id))
            await db.rollback()
    try:
        # A rollback above expires everything the session holds.
        for row in (bud, access.board, target.card):
            await db.refresh(row)
        notice = await stage_owner_notice(db, access, target.card, bud)
        await db.commit()
        send(notice)
    except Exception:
        logger.exception("handover_owner_notice_failed", bud_id=str(bud.id))
        await db.rollback()


async def _actor_name(db: AsyncSession, access: BoardAccess) -> str | None:
    people = await UserRepository(db, org_id=access.org_id).get_people_by_ids({access.user_id})
    person = people.get(access.user_id)
    return person.name if person else None
