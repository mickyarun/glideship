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


"""A BUD's origin card in brief, for a caller who can open the card's board.

The live origin (:func:`app.repositories.board_handover.live_handover`) is
found through the same board access rule as everything else, so a BUD
handed over from a members-only board names no card to anyone off it.
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.board_card_key import BoardCardKeyRepository
from app.repositories.board_handover_origins import BoardHandoverOriginRepository
from app.services.boards.access import BoardCaller
from app.services.boards.reads import card_key


async def origin_card_summary(
    db: AsyncSession, caller: BoardCaller, bud_id: uuid.UUID
) -> dict[str, Any] | None:
    """The card the BUD came from (key, board, title), or None when there's none to show."""
    origins = BoardHandoverOriginRepository(db, org_id=caller.org_id)
    found = await origins.visible_live_origins([bud_id], caller.user_id, caller.perms)
    if not found:
        return None
    key = card_key(found[0].board_key, found[0].card_number)
    keys = BoardCardKeyRepository(db, org_id=caller.org_id)
    resolved = await keys.resolve(key, caller.user_id, caller.perms)
    if resolved is None:
        return None
    card, board, _role = resolved
    return {
        "card_key": key,
        "board_key": board.key,
        "board_name": board.name,
        "title": card.title,
        "archived": card.archived_at is not None,
    }
