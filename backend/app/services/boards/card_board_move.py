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

"""Moving a card to another board: the same row, a new key, the old key kept.

The caller edits both boards. The card lands at the bottom of a stage on
the target (:func:`card_carry.pick_stage`) and meets that stage's entry
rules as it will arrive there: with the labels, assignees and repository
it keeps (:mod:`app.services.boards.card_carry`). It takes the target's
next number, and ``board_card_key_aliases`` remembers the old key. Comments,
checklist, attachments, docs and history stay with the row.

Locks: the kept repository's link, then both stages in id order, then the
card, then the target board's number counter (late, as a create takes it).
Nobody is notified: removed assignees aren't told, and the others hear
nothing new.
"""

import uuid
from dataclasses import replace
from datetime import UTC, datetime
from functools import partial

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board import BoardStage
from app.models.board_enums import BoardCardEventType
from app.repositories.board_card import BoardCardRepository
from app.repositories.board_card_key import BoardCardKeyRepository
from app.repositories.board_card_links import BoardCardLinkRepository
from app.repositories.board_card_summary import BoardCardSummaryRepository, CardSummaryRow
from app.repositories.board_repo import BoardRepoRepository
from app.repositories.board_stage import BoardStageRepository
from app.schemas.boards.card import CardDetail, CardMoveBoard
from app.services.boards.access import BoardAccess, CardAccess, resolve_board_access
from app.services.boards.card_carry import Carry, carry_over, pick_stage
from app.services.boards.card_checks import check_open
from app.services.boards.card_place import STALE_NEIGHBOURS, place_card
from app.services.boards.card_timing import enter_category
from app.services.boards.constants import BOARD_ACTION_MIN_ROLE, DELIVERY_BOARD_KEY, BoardAction
from app.services.boards.errors import BoardConflictError, BoardItemNotFoundError, BoardRuleError
from app.services.boards.events import record_event
from app.services.boards.live import BoardChanges, BoardSocketEvent
from app.services.boards.move_rules import EntryCause, enter_stage
from app.services.boards.reads import card_detail, card_key, summary_json
from app.services.boards.stage_service import STAGE_NOT_FOUND

TO_DELIVERY = "Moving a card to Delivery is a handover."
SAME_BOARD = "The card is already on this board."


async def move_to_board(db: AsyncSession, source: CardAccess, body: CardMoveBoard) -> CardDetail:
    """Move the card to ``body.target_board_key``; the card as it now is there.

    Raises:
        BoardRuleError: The target is Delivery or the card's own board, or
            the target stage's required fields are missing (422).
        BoardNotFoundError / BoardForbiddenError / BoardArchivedError: The
            caller can't see, can't edit, or can't change the target (404/403/409).
        ChecklistOpenError: Completing there with open items, unconfirmed (409).
    """
    access, card = source.access, source.card
    target = await _target(db, access, body.target_board_key)
    check_open(card)
    stage_repo = BoardStageRepository(db, org_id=access.org_id)
    from_stage = await stage_repo.get_in_board(access.board.id, card.stage_id)
    if from_stage is None:
        raise BoardConflictError(STALE_NEIGHBOURS)
    stages = await stage_repo.list_for_board(target.board.id)
    to_stage = pick_stage(stages, from_stage, body.stage_id)
    repo_id = card.repo_id
    links_repo = BoardRepoRepository(db, org_id=access.org_id)
    keep_repo = repo_id is not None and await links_repo.hold_link(target.board.id, repo_id)
    await _lock_stages(db, access, target, from_stage, to_stage)
    cards = BoardCardRepository(db, org_id=access.org_id)
    await cards.lock(card)
    check_open(card)
    if (card.board_id, card.stage_id, card.repo_id) != (access.board.id, from_stage.id, repo_id):
        raise BoardConflictError(STALE_NEIGHBOURS)
    carry = await carry_over(db, access, target, card)
    kept_repo = repo_id if keep_repo else None
    await enter_stage(
        to_stage,
        cause=EntryCause.MOVE_BOARD,
        from_stage=from_stage,
        facts=partial(_facts, db, access, card.id, carry, kept_repo),
        confirm_open_checklist=body.confirm_open_checklist,
    )
    links = BoardCardLinkRepository(db, org_id=access.org_id)
    # The old board's labels go before the card's board changes under them.
    await links.set_labels(card, [])
    await links.set_assignees(card, carry.assignee_ids)
    placement = await place_card(db, access.org_id, to_stage, card_id=card.id)
    old_key = card_key(access.board, card.number)
    BoardCardKeyRepository(db, org_id=access.org_id).add_alias(card, access.board.id, card.number)
    (number,) = await cards.allocate_card_numbers(target.board.id, 1)
    # One UPDATE: board, number, stage and repository change together, so
    # the composite keys never see the card half-moved.
    card.board_id, card.number, card.stage_id = target.board.id, number, to_stage.id
    card.position, card.repo_id = placement.position, kept_repo
    enter_category(card, to_stage.category, datetime.now(UTC))
    await db.flush()
    await links.set_labels(card, carry.label_ids)
    await record_event(
        db,
        card,
        BoardCardEventType.MOVED_BOARD,
        actor_id=access.user_id,
        to_stage=to_stage,
        detail={
            "from_board": _board_ref(access),
            "to_board": _board_ref(target),
            "from_stage": {"id": str(from_stage.id), "name": from_stage.name},
            "old_key": old_key,
            "new_key": card_key(target.board, number),
            "dropped_labels": carry.dropped_labels,
            "removed_assignees": [str(u) for u in carry.removed_assignees],
            "cleared_repo": None if keep_repo or repo_id is None else str(repo_id),
        },
    )
    detail = await card_detail(db, target.board, card)
    left = BoardChanges.of(access)
    left.emit(
        BoardSocketEvent.CARD_LEFT_BOARD,
        card_id=str(card.id),
        new_key=detail.key,
        to_board_key=target.board.key,
    )
    arrived = BoardChanges.of(target)
    if placement.rebalanced:
        arrived.emit(BoardSocketEvent.STAGE_REORDERED, stage_id=str(to_stage.id))
    arrived.emit(BoardSocketEvent.CARD_CREATED, card=summary_json(detail))
    left.queue(db)
    await arrived.commit(db)
    return detail


async def _target(db: AsyncSession, access: BoardAccess, raw_key: str) -> BoardAccess:
    key = raw_key.strip().upper()
    if key == DELIVERY_BOARD_KEY:
        raise BoardRuleError(TO_DELIVERY)
    if key == access.board.key:
        raise BoardRuleError(SAME_BOARD)
    return await resolve_board_access(
        db,
        user_id=access.user_id,
        org_id=access.org_id,
        perms=access.perms,
        key=key,
        min_role=BOARD_ACTION_MIN_ROLE[BoardAction.MOVE_CARD],
        writable=True,
        origin=access.origin,
    )


async def _lock_stages(
    db: AsyncSession,
    source: BoardAccess,
    target: BoardAccess,
    from_stage: BoardStage,
    to_stage: BoardStage,
) -> None:
    """Both stages, in id order: the order every card writer locks stages in."""
    repo = BoardStageRepository(db, org_id=source.org_id)
    pairs = sorted(
        [(from_stage.id, source.board.id, True), (to_stage.id, target.board.id, False)],
        key=lambda pair: str(pair[0]),
    )
    for stage_id, board_id, is_source in pairs:
        if await repo.lock(board_id, stage_id) is None:
            # Deleted since it was read.
            if is_source:
                raise BoardConflictError(STALE_NEIGHBOURS)
            raise BoardItemNotFoundError(STAGE_NOT_FOUND)


async def _facts(
    db: AsyncSession,
    access: BoardAccess,
    card_id: uuid.UUID,
    carry: Carry,
    repo_id: uuid.UUID | None,
) -> CardSummaryRow:
    """The card's facts as it will arrive: only what it keeps on the target."""
    summaries = BoardCardSummaryRepository(db, org_id=access.org_id)
    (row,) = await summaries.summaries_by_ids(access.board.id, [card_id])
    return replace(
        row, assignee_ids=carry.assignee_ids, label_ids=carry.label_ids, repo_id=repo_id
    )


def _board_ref(access: BoardAccess) -> dict[str, str]:
    return {"id": str(access.board.id), "key": access.board.key, "name": access.board.name}
