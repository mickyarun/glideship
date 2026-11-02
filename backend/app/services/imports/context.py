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


"""The context every import write runs under.

``silent`` (the default, and what every import uses) suppresses exactly
one thing: the per-card ``card_created`` socket event the writer passes to
:meth:`ImportContext.announce`. Each suppressed event is counted in
``suppressed`` and reported as the result's ``suppressed_events``.
Notifications, assignment DMs and ``on_enter`` stage agents aren't
suppressed here because import writes never call the services that send
them. Each card gets one ``imported`` history entry instead, and the board
hears a single ``board_imported`` summary when the run ends.

Per batch the context locks the board's stages, then claims every card
number the batch needs in one ``allocate_card_numbers`` call, the same
stage-then-board lock order a single card create uses. A card that fails
gives its number back to the next card, and numbers still unused at the
end of the batch are released, so numbering stays contiguous. Positions go
to the bottom of each stage, in the order items arrive.
"""

import uuid
from collections import Counter, deque
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.board import Board, BoardStage
from app.models.external_import import ExternalImportSession
from app.repositories.board_card import BoardCardRepository
from app.repositories.board_card_position import BoardCardPositionRepository
from app.repositories.board_stage import BoardStageRepository
from app.services.boards.access import BoardAccess
from app.services.boards.live import BoardChanges, BoardSocketEvent


@dataclass
class ByteBudget:
    """How many attachment bytes the import may still copy.

    ``limit`` already folds in the per-import cap and what the org may copy
    today; ``spent`` starts from what earlier runs of the session copied.
    """

    limit: int
    spent: int = 0

    @property
    def remaining(self) -> int:
        """Bytes left; never negative."""
        return max(self.limit - self.spent, 0)

    def spend(self, size: int) -> None:
        """Count ``size`` bytes against the budget."""
        self.spent += size

    def refund(self, size: int) -> None:
        """Give back bytes of a copy that was deleted unused."""
        self.spent = max(self.spent - size, 0)


class ImportContext:
    """The target board, the importer, and what one run has done so far."""

    def __init__(
        self,
        db: AsyncSession,
        access: BoardAccess,
        session: ExternalImportSession,
        budget: ByteBudget,
        *,
        silent: bool = True,
    ) -> None:
        self.db = db
        self.access = access
        self.session = session
        self.silent = silent
        self.budget = budget
        # What written cards left out or cut, reported in the result.
        self.counters: Counter[str] = Counter()
        self.suppressed = 0
        self._numbers: deque[int] = deque()
        self._item_numbers: list[int] = []
        self._positions: dict[uuid.UUID, float] = {}
        self._changes = BoardChanges.of(access)

    @property
    def board(self) -> Board:
        """The board items are written to."""
        return self.access.board

    @property
    def org_id(self) -> uuid.UUID:
        """The org everything is written in."""
        return self.access.org_id

    @property
    def actor_id(self) -> uuid.UUID:
        """Who runs the import; imported cards are created by them."""
        return self.access.user_id

    async def lock_stages(self) -> None:
        """Lock the board's stages for the rest of the batch's transaction."""
        await BoardStageRepository(self.db, org_id=self.org_id).lock_board_stages(self.board.id)
        self._positions.clear()

    async def claim_numbers(self, cards: int) -> None:
        """Claim ``cards`` card numbers in one statement; holds the board row until commit."""
        self._numbers.clear()
        if cards:
            repo = BoardCardRepository(self.db, org_id=self.org_id)
            self._numbers.extend(await repo.allocate_card_numbers(self.board.id, cards))

    def start_item(self) -> None:
        """Begin one item: numbers it takes are given back if it fails."""
        self._item_numbers = []

    def take_number(self) -> int:
        """The next number claimed for this batch."""
        if not self._numbers:
            raise RuntimeError("the batch claimed fewer card numbers than it writes")
        number = self._numbers.popleft()
        self._item_numbers.append(number)
        return number

    def item_failed(self) -> None:
        """Put the failed item's numbers back at the front, for the next item."""
        self._numbers.extendleft(reversed(self._item_numbers))
        self._item_numbers = []

    async def release_unused_numbers(self) -> None:
        """Hand back the numbers failed items left at the end of the claim."""
        if self._numbers:
            unused = range(self._numbers[0], self._numbers[-1] + 1)
            repo = BoardCardRepository(self.db, org_id=self.org_id)
            await repo.release_card_numbers(self.board.id, unused)
            self._numbers.clear()

    async def next_position(self, stage: BoardStage) -> float:
        """A position below everything already in ``stage``, in arrival order."""
        last = self._positions.get(stage.id)
        if last is None:
            repo = BoardCardPositionRepository(self.db, org_id=self.org_id)
            last = await repo.last_position(stage.id) or 0.0
        position = last + settings.boards.position_gap
        self._positions[stage.id] = position
        return position

    def announce(self, event: BoardSocketEvent, **payload: Any) -> None:
        """Queue a live event for the batch, unless the import is silent."""
        if self.silent:
            self.suppressed += 1
            return
        self._changes.emit(event, **payload)

    async def commit_batch(self) -> None:
        """Commit the batch, sending whatever it announced."""
        await self._changes.commit(self.db)
        self._changes = BoardChanges.of(self.access)

    async def finish(self, summary: dict[str, Any]) -> None:
        """Commit the end of the run with one summary event for the board."""
        self._changes.emit(BoardSocketEvent.BOARD_IMPORTED, **summary)
        await self.commit_batch()
