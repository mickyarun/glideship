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

"""Origin chips for the Delivery board: the card each listed BUD came from.

A BUD's chip names its live origin card only to a caller who holds a role
on that card's board; anyone else sees no chip, as for a BUD never handed
over, so a members-only board's key never reaches them.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.board_handover_origins import BoardHandoverOriginRepository
from app.schemas.bud import BUDListOrigin
from app.services.boards.access import BoardCaller
from app.services.boards.reads import card_key


async def list_origins(
    db: AsyncSession, caller: BoardCaller, bud_ids: list[uuid.UUID]
) -> dict[uuid.UUID, BUDListOrigin]:
    """Each BUD's visible live origin, by BUD id, in one query for the whole page."""
    repo = BoardHandoverOriginRepository(db, org_id=caller.org_id)
    rows = await repo.visible_live_origins(bud_ids, caller.user_id, caller.perms)
    return {
        row.bud_id: BUDListOrigin(
            card_key=card_key(row.board_key, row.card_number), board_key=row.board_key
        )
        for row in rows
    }
