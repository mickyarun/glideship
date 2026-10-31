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

"""A card's handovers as the API returns them."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.board_handover import BoardHandoverRepository, HandoverRow
from app.schemas.boards.handover import HandoverList, HandoverRead
from app.services.boards.access import CardAccess
from app.services.boards.handover_rules import can_hand_over
from app.services.boards.handover_similar import bud_key


def handover_read(row: HandoverRow) -> HandoverRead:
    """One handover, with its BUD's key, title and status (null once the BUD is gone)."""
    handover, bud = row
    return HandoverRead(
        id=handover.id,
        card_id=handover.card_id,
        status=handover.status,
        linked_existing=handover.linked_existing,
        target_status=handover.target_status,
        bud_id=handover.bud_id,
        bud_key=bud_key(bud.number) if bud else None,
        bud_title=bud.title if bud else None,
        bud_status=bud.status if bud else None,
        handed_over_by=handover.handed_over_by,
        handed_over_at=handover.handed_over_at,
        returned_at=handover.returned_at,
        return_reason=handover.return_reason,
    )


async def list_handovers(db: AsyncSession, target: CardAccess) -> HandoverList:
    """The card's handovers, oldest first, and whether the caller may add one now."""
    repo = BoardHandoverRepository(db, org_id=target.access.org_id)
    rows = await repo.list_for_card(target.card.id)
    return HandoverList(
        items=[handover_read(row) for row in rows],
        can_hand_over=can_hand_over(target.access, target.card),
    )
