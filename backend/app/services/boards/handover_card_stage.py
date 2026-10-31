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

"""The card's side of a handover: locks, and its move to the handover stage.

Locks follow the order every card writer uses: the card's stage and the
board's handover stage in id order, then the card. Holding the card's row
serialises handovers of one card, so a double click waits here and then
finds the first one's row by its idempotency key.

On the card's first handover it moves to the bottom of the handover stage
(category ``done``) through :func:`enter_stage` with ``EntryCause.HANDOVER``,
so the stage's required fields and the open-checklist rule apply as on any
move. Later handovers leave it where it is.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board import BoardStage
from app.repositories.board_card import BoardCardRepository
from app.repositories.board_card_summary import BoardCardSummaryRepository, CardSummaryRow
from app.repositories.board_stage import BoardStageRepository
from app.services.boards.access import CardAccess
from app.services.boards.agents.trigger import queue_entry_agents
from app.services.boards.card_checks import check_open
from app.services.boards.card_place import STALE_NEIGHBOURS, place_card
from app.services.boards.card_timing import enter_category
from app.services.boards.errors import BoardConflictError
from app.services.boards.move_rules import EntryCause, enter_stage


@dataclass(frozen=True)
class CardStage:
    """Where the card was, where the handover put it, and whether its stage was respaced."""

    from_stage: BoardStage
    to_stage: BoardStage | None
    rebalanced: bool = False

    @property
    def moved(self) -> bool:
        """Whether the card changed stage."""
        return self.to_stage is not None


@dataclass(frozen=True)
class LockedCard:
    """The locked card's stage, and the board's handover stage (None when unset)."""

    from_stage: BoardStage
    handover_stage: BoardStage | None


async def lock_card(db: AsyncSession, target: CardAccess) -> LockedCard:
    """Lock the card's stage, the handover stage and the card, in that order.

    Raises:
        BoardConflictError: The card is archived, or moved since it was read.
    """
    access, card = target.access, target.card
    handover_stage_id = access.board.handover_stage_id
    wanted = {card.stage_id} | ({handover_stage_id} if handover_stage_id else set())
    stages = await BoardStageRepository(db, org_id=access.org_id).lock_stages(
        access.board.id, wanted
    )
    await BoardCardRepository(db, org_id=access.org_id).lock(card)
    check_open(card)
    from_stage = stages.get(card.stage_id)
    if from_stage is None:
        raise BoardConflictError(STALE_NEIGHBOURS)
    handover_stage = stages.get(handover_stage_id) if handover_stage_id else None
    return LockedCard(from_stage=from_stage, handover_stage=handover_stage)


async def move_on_first_handover(
    db: AsyncSession,
    target: CardAccess,
    locked: LockedCard,
    *,
    first: bool,
    confirm_open_checklist: bool,
) -> CardStage:
    """Put the card at the bottom of the handover stage when this is its first handover.

    Raises:
        StageRequirementsMissingError: The handover stage requires a field the card lacks.
        ChecklistOpenError: Open checklist items, and the caller hasn't confirmed.
    """
    access, card = target.access, target.card
    from_stage, to_stage = locked.from_stage, locked.handover_stage
    if not first or to_stage is None or to_stage.id == from_stage.id:
        return CardStage(from_stage=from_stage, to_stage=None)
    await enter_stage(
        to_stage,
        cause=EntryCause.HANDOVER,
        from_stage=from_stage,
        facts=partial(_summary, db, target),
        confirm_open_checklist=confirm_open_checklist,
    )
    placement = await place_card(db, access.org_id, to_stage, card_id=card.id)
    if placement.rebalanced:
        # The respacing wrote positions behind the session's back.
        await BoardCardRepository(db, org_id=access.org_id).lock(card)
    card.position = placement.position
    card.stage_id = to_stage.id
    enter_category(card, to_stage.category, datetime.now(UTC))
    # ENTRY_RULES: a handover starts no agent on the handover stage.
    await queue_entry_agents(
        db, board=access.board, card=card, stage=to_stage, cause=EntryCause.HANDOVER
    )
    return CardStage(from_stage=from_stage, to_stage=to_stage, rebalanced=placement.rebalanced)


async def _summary(db: AsyncSession, target: CardAccess) -> CardSummaryRow:
    summaries = BoardCardSummaryRepository(db, org_id=target.access.org_id)
    (row,) = await summaries.summaries_by_ids(target.access.board.id, [target.card.id])
    return row
