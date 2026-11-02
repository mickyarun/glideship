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

"""The card's side of sending a BUD back: locks, the comment, and the move to the return stage.

The caller already holds the BUD's row lock. The card's stage and the
board's return stage are locked in id order, then the card, as every card
writer does. When the card holds no other live handover it moves to the
bottom of ``return_stage_id`` (category ``todo``) through :func:`enter_stage`
with ``EntryCause.RETURN``, which applies no entry rules: nobody chose the
stage, and the card must get there whatever it lacks. An archived card, an
archived board or a board without a return stage leaves the card where it is.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board import Board, BoardStage
from app.models.board_card import BoardCard
from app.models.board_card_detail import BoardCardComment
from app.models.board_enums import BoardStatus
from app.repositories.board import BoardRepository
from app.repositories.board_card import BoardCardRepository
from app.repositories.board_stage import BoardStageRepository
from app.services.boards.agents.trigger import queue_entry_agents
from app.services.boards.card_place import STALE_NEIGHBOURS, place_card
from app.services.boards.card_timing import enter_category
from app.services.boards.comment_service import post_comment
from app.services.boards.errors import BoardConflictError
from app.services.boards.move_rules import EntryCause, enter_stage


@dataclass(frozen=True)
class ReturnCard:
    """The locked card, its board, the stage it's in and the board's return stage."""

    board: Board
    card: BoardCard
    from_stage: BoardStage
    return_stage: BoardStage | None


@dataclass(frozen=True)
class ReturnMove:
    """Where the card went, if it moved, and whether that stage was respaced."""

    to_stage: BoardStage | None
    rebalanced: bool = False


async def lock_card(db: AsyncSession, org_id: uuid.UUID, card_id: uuid.UUID) -> ReturnCard:
    """Lock the card's stage, the return stage and the card, in that order.

    Raises:
        BoardConflictError: The card moved while it was being locked; retry.
    """
    cards = BoardCardRepository(db, org_id=org_id)
    card = await cards.get_by_id(card_id)
    board = await BoardRepository(db, org_id=org_id).get_by_id(card.board_id) if card else None
    if card is None or board is None:
        raise BoardConflictError(STALE_NEIGHBOURS)
    wanted = {card.stage_id} | ({board.return_stage_id} if board.return_stage_id else set())
    stages = await BoardStageRepository(db, org_id=org_id).lock_stages(board.id, wanted)
    await cards.lock(card)
    from_stage = stages.get(card.stage_id)
    if from_stage is None or card.board_id != board.id:
        raise BoardConflictError(STALE_NEIGHBOURS)
    return_stage = stages.get(board.return_stage_id) if board.return_stage_id else None
    return ReturnCard(board=board, card=card, from_stage=from_stage, return_stage=return_stage)


async def move_to_return_stage(db: AsyncSession, locked: ReturnCard) -> ReturnMove:
    """Put the card at the bottom of the return stage, when it can go there."""
    card, to_stage = locked.card, locked.return_stage
    stays = (
        to_stage is None
        or to_stage.id == locked.from_stage.id
        or card.archived_at is not None
        or locked.board.status is BoardStatus.ARCHIVED
    )
    if stays or to_stage is None:
        return ReturnMove(to_stage=None)
    await enter_stage(to_stage, cause=EntryCause.RETURN, from_stage=locked.from_stage)
    placement = await place_card(db, card.org_id, to_stage, card_id=card.id)
    if placement.rebalanced:
        # The respacing wrote positions behind the session's back.
        await BoardCardRepository(db, org_id=card.org_id).lock(card)
    card.position = placement.position
    card.stage_id = to_stage.id
    enter_category(card, to_stage.category, datetime.now(UTC))
    # ENTRY_RULES: a BUD sent back starts no agent on the return stage.
    await queue_entry_agents(
        db, board=locked.board, card=card, stage=to_stage, cause=EntryCause.RETURN
    )
    return ReturnMove(to_stage=to_stage, rebalanced=placement.rebalanced)


async def post_reason(
    db: AsyncSession, card: BoardCard, *, author_id: uuid.UUID, lead: str, reason: str
) -> BoardCardComment:
    """The reason as a comment on the card, written by whoever sent the BUD back.

    Posted as any comment is (with its ``commented`` event); the returned
    notice is the only one sent, so no comment notice goes out.
    """
    return await post_comment(db, card, author_id=author_id, body=f"{lead}{reason}")
