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

"""Pick a card's position in a stage from the neighbours it should sit between.

The caller holds the stage's row lock. When the neighbours are too close to
split, the stage is respaced once and the neighbours read again.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.board import BoardStage
from app.repositories.board_card_position import BoardCardPositionRepository
from app.services.boards.errors import BoardConflictError, BoardRuleError
from app.services.boards.positions import position_between

STALE_NEIGHBOURS = "The board changed while you were moving this card; reload and try again."


@dataclass(frozen=True)
class Placement:
    """Where the card goes, and whether the stage was respaced to make room."""

    position: float
    rebalanced: bool


async def place_card(
    db: AsyncSession,
    org_id: uuid.UUID,
    stage: BoardStage,
    *,
    card_id: uuid.UUID | None = None,
    after_id: uuid.UUID | None = None,
    before_id: uuid.UUID | None = None,
) -> Placement:
    """A position below ``after_id`` and above ``before_id`` (the bottom when neither)."""
    if card_id is not None and card_id in (after_id, before_id):
        raise BoardRuleError("A card can't be placed next to itself.")
    positions = BoardCardPositionRepository(db, org_id=org_id)
    rebalanced = False
    while True:
        lo, hi = await _neighbours(positions, stage.id, card_id, after_id, before_id)
        position = position_between(lo, hi)
        if position is not None:
            return Placement(position=position, rebalanced=rebalanced)
        if rebalanced:
            # A fresh respacing always leaves a full gap; this is unreachable
            # unless the settings are inconsistent.
            raise BoardConflictError(STALE_NEIGHBOURS)
        await positions.rebalance(stage.id, settings.boards.position_gap)
        rebalanced = True


async def _neighbours(
    positions: BoardCardPositionRepository,
    stage_id: uuid.UUID,
    card_id: uuid.UUID | None,
    after_id: uuid.UUID | None,
    before_id: uuid.UUID | None,
) -> tuple[float | None, float | None]:
    lo = await _anchor(positions, stage_id, after_id)
    hi = await _anchor(positions, stage_id, before_id)
    if after_id is not None and before_id is not None:
        assert lo is not None and hi is not None
        if (lo, str(after_id)) >= (hi, str(before_id)):
            raise BoardConflictError(STALE_NEIGHBOURS)
        return lo, hi
    if after_id is not None:
        assert lo is not None
        return lo, await positions.next_after(stage_id, after_id, lo, card_id)
    if before_id is not None:
        assert hi is not None
        return await positions.previous_before(stage_id, before_id, hi, card_id), hi
    return await positions.last_position(stage_id, card_id), None


async def _anchor(
    positions: BoardCardPositionRepository, stage_id: uuid.UUID, anchor_id: uuid.UUID | None
) -> float | None:
    if anchor_id is None:
        return None
    position = await positions.position_of(stage_id, anchor_id)
    if position is None:
        # Moved, archived or gone since the client last looked.
        raise BoardConflictError(STALE_NEIGHBOURS)
    return position
