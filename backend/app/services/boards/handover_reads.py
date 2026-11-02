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

"""A card's handovers as the API and the board's live events show them.

Anyone who sees the card sees each handover's BUD key and statuses; the
BUD's title only goes to callers who may open it (``buds:view`` and
``workspace:engineering``). Board topics carry ids, keys and statuses only.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.board_handover import BoardHandoverRepository, HandoverRow
from app.schemas.boards.handover import HandoverList, HandoverRead
from app.services.boards.access import CardAccess
from app.services.boards.handover_chips import opens_buds
from app.services.boards.handover_history import History, history_by_bud
from app.services.boards.handover_rules import can_hand_over
from app.services.boards.handover_similar import bud_key


def handover_read(
    row: HandoverRow, *, can_open_bud: bool, history: History | None = None
) -> HandoverRead:
    """One handover, with its BUD's key and status (null once the BUD is gone).

    ``history`` is the card's (:func:`history_by_bud`); left out, none is shown.
    """
    handover, bud = row
    return HandoverRead(
        id=handover.id,
        card_id=handover.card_id,
        status=handover.status,
        linked_existing=handover.linked_existing,
        target_status=handover.target_status,
        bud_id=handover.bud_id,
        bud_key=bud_key(bud.number) if bud else None,
        bud_title=bud.title if bud and can_open_bud else None,
        bud_status=bud.status if bud else None,
        handed_over_by=handover.handed_over_by,
        handed_over_at=handover.handed_over_at,
        returned_at=handover.returned_at,
        return_reason=handover.return_reason,
        can_open_bud=can_open_bud,
        stage_start_failed=handover.stage_start_failed_at is not None,
        history=(history or {}).get(handover.bud_id, []) if handover.bud_id else [],
    )


def live_handover(read: HandoverRead) -> dict[str, Any]:
    """A handover as a board topic carries it: ids, the key and statuses."""
    return {
        "id": str(read.id),
        "bud_id": str(read.bud_id) if read.bud_id else None,
        "bud_key": read.bud_key,
        "bud_status": read.bud_status.value if read.bud_status else None,
        "status": read.status.value,
    }


async def list_handovers(db: AsyncSession, target: CardAccess) -> HandoverList:
    """The card's handovers, oldest first, and whether the caller may add one now."""
    repo = BoardHandoverRepository(db, org_id=target.access.org_id)
    opens = opens_buds(target.access.perms)
    rows = await repo.list_for_card(target.card.id)
    history = await history_by_bud(db, target.access.org_id, target.card.id) if rows else {}
    return HandoverList(
        items=[handover_read(row, can_open_bud=opens, history=history) for row in rows],
        can_hand_over=can_hand_over(target.access, target.card),
    )
