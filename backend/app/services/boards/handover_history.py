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

"""Each of a card's handovers' send-backs and re-handovers, newest first.

Built from the card's ``returned`` and ``handed_over`` (``again``) events,
so it shows what the card's activity already shows to anyone on the
board: when, who, and a send-back's reason (posted there as a comment).
"""

import uuid
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.board_enums import BoardCardEventType
from app.repositories.board_handover_history import BoardHandoverHistoryRepository
from app.schemas.boards.card import (
    CardDetail,
    HandoverChip,
    HandoverHistoryEntry,
    HandoverHistoryKind,
)

History = dict[uuid.UUID, list[HandoverHistoryEntry]]


async def history_by_bud(db: AsyncSession, org_id: uuid.UUID, card_id: uuid.UUID) -> History:
    """The card's history keyed by BUD id, in one query."""
    repo = BoardHandoverHistoryRepository(db, org_id=org_id)
    rows = await repo.for_card(card_id, per_bud=settings.boards.handover_history_limit)
    found: History = defaultdict(list)
    for row in rows:
        returned = row.type is BoardCardEventType.RETURNED
        found[uuid.UUID(row.bud_id)].append(
            HandoverHistoryEntry(
                at=row.at,
                kind=HandoverHistoryKind.RETURNED
                if returned
                else HandoverHistoryKind.HANDED_OVER_AGAIN,
                reason=row.reason if returned else None,
                by_name=row.by_name,
            )
        )
    return dict(found)


def with_history(chips: list[HandoverChip], history: History) -> list[HandoverChip]:
    """The chips, each with its BUD's history."""
    return [chip.model_copy(update={"history": history.get(chip.bud_id, [])}) for chip in chips]


def chip_history(detail: CardDetail) -> History:
    """The history a card's detail already loaded onto its chips, by BUD id."""
    return {chip.bud_id: chip.history for chip in detail.handovers}
