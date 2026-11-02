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

"""Put a card on another board: the write every board-to-board path shares.

Moving a card between boards and handing one over both end here. The
caller has already checked access, locked the kept repository's link, both
stages and the card, worked out what the card keeps
(:func:`app.services.boards.card_carry.carry_over`) and checked the target
stage's entry rules. This swaps the labels and assignees, keeps the old key
as an alias, takes the target's next number (late, as a create takes it),
places the card at the bottom of ``to_stage`` and records one history event
on the target board.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board import Board, BoardStage
from app.models.board_card import BoardCard
from app.models.board_enums import BoardCardEventType
from app.repositories.board_card import BoardCardRepository
from app.repositories.board_card_key import BoardCardKeyRepository
from app.repositories.board_card_links import BoardCardLinkRepository
from app.services.boards.card_carry import Carry
from app.services.boards.card_place import Placement, place_card
from app.services.boards.card_timing import enter_category
from app.services.boards.events import record_event
from app.services.boards.reads import card_key


@dataclass(frozen=True)
class Relocation:
    """Where the card goes, from where, and what it keeps on the way."""

    source: Board
    target: Board
    from_stage: BoardStage
    to_stage: BoardStage
    carry: Carry


@dataclass(frozen=True)
class Relocated:
    """The card's old and new keys, and how it was placed in the target stage."""

    old_key: str
    new_key: str
    placement: Placement


async def relocate_card(
    db: AsyncSession,
    card: BoardCard,
    move: Relocation,
    *,
    actor_id: uuid.UUID,
    event_type: BoardCardEventType = BoardCardEventType.MOVED_BOARD,
) -> Relocated:
    """Write ``card`` onto ``move.target``; flushed, not committed."""
    org_id, carry, to_stage = card.org_id, move.carry, move.to_stage
    links = BoardCardLinkRepository(db, org_id=org_id)
    # The old board's labels go before the card's board changes under them.
    await links.set_labels(card, [])
    await links.set_assignees(card, carry.assignee_ids)
    placement = await place_card(db, org_id, to_stage, card_id=card.id)
    old_key = card_key(move.source.key, card.number)
    BoardCardKeyRepository(db, org_id=org_id).add_alias(card, move.source.id, card.number)
    cards = BoardCardRepository(db, org_id=org_id)
    (number,) = await cards.allocate_card_numbers(move.target.id, 1)
    # One UPDATE: board, number, stage and repository change together, so
    # the composite keys never see the card half-moved.
    card.board_id, card.number, card.stage_id = move.target.id, number, to_stage.id
    card.position, card.repo_id = placement.position, carry.repo_id
    enter_category(card, to_stage.category, datetime.now(UTC))
    await db.flush()
    await links.set_labels(card, carry.label_ids)
    new_key = card_key(move.target.key, number)
    await record_event(
        db,
        card,
        event_type,
        actor_id=actor_id,
        to_stage=to_stage,
        # A done card moved to a done stage elsewhere isn't a completion.
        from_category=move.from_stage.category,
        detail={
            "from_board": _board_ref(move.source),
            "to_board": _board_ref(move.target),
            "from_stage": {"id": str(move.from_stage.id), "name": move.from_stage.name},
            "old_key": old_key,
            "new_key": new_key,
            "dropped_labels": carry.dropped_labels,
            "removed_assignees": [str(u) for u in carry.removed_assignees],
            "cleared_repo": None if carry.cleared_repo is None else str(carry.cleared_repo),
        },
    )
    return Relocated(old_key=old_key, new_key=new_key, placement=placement)


def _board_ref(board: Board) -> dict[str, str]:
    return {"id": str(board.id), "key": board.key, "name": board.name}
