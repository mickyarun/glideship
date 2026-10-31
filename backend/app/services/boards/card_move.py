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

"""Moving a card within its board, and archiving or restoring it.

Moves lock the target stage row before reading neighbours, so concurrent
moves into one stage take turns. A move to another stage must meet that
stage's entry rules (:mod:`app.services.boards.move_rules`) and records a
``moved`` event with both categories frozen; reordering inside a stage
checks and records nothing. Restoring an archived card puts it back in its
own stage, which the entry rules skip.
"""

import uuid
from datetime import UTC, datetime
from functools import partial

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board import BoardStage
from app.models.board_enums import BoardCardEventType
from app.repositories.board_card import BoardCardRepository
from app.repositories.board_card_summary import BoardCardSummaryRepository, CardSummaryRow
from app.repositories.board_stage import BoardStageRepository
from app.schemas.boards.card import CardDetail, CardMove
from app.services.boards.access import CardAccess
from app.services.boards.card_checks import check_open
from app.services.boards.card_place import STALE_NEIGHBOURS, place_card
from app.services.boards.card_timing import enter_category
from app.services.boards.errors import BoardConflictError, BoardItemNotFoundError
from app.services.boards.events import record_event
from app.services.boards.handover_chips import opens_buds
from app.services.boards.live import BoardChanges, BoardSocketEvent
from app.services.boards.move_rules import EntryCause, enter_stage
from app.services.boards.reads import card_detail, summary_json
from app.services.boards.stage_service import STAGE_NOT_FOUND


async def _locked_stage(db: AsyncSession, target: CardAccess, stage_id: uuid.UUID) -> BoardStage:
    repo = BoardStageRepository(db, org_id=target.access.org_id)
    stage = await repo.lock(target.access.board.id, stage_id)
    if stage is None:
        raise BoardItemNotFoundError(STAGE_NOT_FOUND)
    return stage


async def move_card(db: AsyncSession, target: CardAccess, body: CardMove) -> CardDetail:
    """Put the card in ``body.stage_id`` between the given neighbours."""
    access, card = target.access, target.card
    cards = BoardCardRepository(db, org_id=access.org_id)
    # Source and target stage first, in id order, then the card: the order
    # a stage delete uses, so the two can't deadlock.
    stages = await BoardStageRepository(db, org_id=access.org_id).lock_stages(
        access.board.id, {body.stage_id, card.stage_id}
    )
    to_stage = stages.get(body.stage_id)
    if to_stage is None:
        raise BoardItemNotFoundError(STAGE_NOT_FOUND)
    await cards.lock(card)
    check_open(card)
    from_stage = stages.get(card.stage_id)
    if from_stage is None:
        # Moved by someone else between loading and locking.
        raise BoardConflictError(STALE_NEIGHBOURS)
    known = await enter_stage(
        to_stage,
        cause=EntryCause.MOVE,
        from_stage=from_stage,
        facts=partial(_summary, db, target),
        confirm_open_checklist=body.confirm_open_checklist,
    )
    placement = await place_card(
        db,
        access.org_id,
        to_stage,
        card_id=card.id,
        after_id=body.after_id,
        before_id=body.before_id,
    )
    if placement.rebalanced:
        # The respacing wrote positions behind the session's back.
        await cards.lock(card)
    card.position = placement.position
    if to_stage.id != card.stage_id:
        card.stage_id = to_stage.id
        enter_category(card, to_stage.category, datetime.now(UTC))
        await record_event(
            db,
            card,
            BoardCardEventType.MOVED,
            actor_id=access.user_id,
            from_stage=from_stage,
            to_stage=to_stage,
        )
    detail = await card_detail(
        db, access.board, card, known=known, opens_buds=opens_buds(access.perms)
    )
    changes = BoardChanges.of(access)
    if placement.rebalanced:
        changes.emit(BoardSocketEvent.STAGE_REORDERED, stage_id=str(to_stage.id))
    # The stage it left, so a client can keep both counts without a reload.
    changes.emit(
        BoardSocketEvent.CARD_MOVED, card=summary_json(detail), from_stage_id=str(from_stage.id)
    )
    await changes.commit(db)
    return detail


async def _summary(db: AsyncSession, target: CardAccess) -> CardSummaryRow:
    summaries = BoardCardSummaryRepository(db, org_id=target.access.org_id)
    (row,) = await summaries.summaries_by_ids(target.access.board.id, [target.card.id])
    return row


async def set_card_archived(db: AsyncSession, target: CardAccess, *, archived: bool) -> CardDetail:
    """Archive the card, or restore it to the bottom of its stage."""
    access, card = target.access, target.card
    cards = BoardCardRepository(db, org_id=access.org_id)
    # An archived card can't move, so its stage is stable while we lock it.
    stage = None if archived else await _locked_stage(db, target, card.stage_id)
    await cards.lock(card)
    if (card.archived_at is not None) == archived:
        return await card_detail(db, access.board, card, opens_buds=opens_buds(access.perms))
    changes = BoardChanges.of(access)
    if stage is None:
        card.archived_at = datetime.now(UTC)
        event, socket = BoardCardEventType.ARCHIVED, BoardSocketEvent.CARD_ARCHIVED
    else:
        placement = await place_card(db, access.org_id, stage, card_id=card.id)
        if placement.rebalanced:
            await cards.lock(card)
            changes.emit(BoardSocketEvent.STAGE_REORDERED, stage_id=str(stage.id))
        await enter_stage(stage, cause=EntryCause.RESTORE)
        card.archived_at, card.position = None, placement.position
        event, socket = BoardCardEventType.RESTORED, BoardSocketEvent.CARD_RESTORED
    await record_event(db, card, event, actor_id=access.user_id)
    detail = await card_detail(db, access.board, card, opens_buds=opens_buds(access.perms))
    changes.emit(socket, card=summary_json(detail))
    await changes.commit(db)
    return detail
