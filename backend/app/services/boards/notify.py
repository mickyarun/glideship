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

"""Tell a BUD's origin card that the BUD was delivered.

:func:`notify_origin_card` runs from :func:`app.services.bud_closure.on_bud_closed`,
the single entry point for prod and close from both the status PATCH and the
auto-close, inside its transaction:

- the card holding the BUD's live handover gets one ``delivered`` event per
  BUD (a second firing, at close after prod, finds it and adds nothing);
- the card's assignees get an in-app row and a DM (``board_handovers``),
  sent once the close commits;
- when that leaves every live handover on the card at prod or closed, the
  card gets ``fully_delivered``.

Open boards hear ``card_handovers_changed {card_id}`` after the commit. No
XP or SP is involved.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_enums import BoardCardEventType
from app.models.bud import BUDDocument
from app.repositories.board import BoardRepository
from app.repositories.board_card import BoardCardRepository
from app.repositories.board_card_event import BoardCardEventRepository
from app.repositories.board_handover import BoardHandoverRepository
from app.services.after_commit import call_after_commit
from app.services.boards import handover_notices
from app.services.boards.events import record_event
from app.services.boards.handover_chips import DELIVERED_STATUSES, all_delivered
from app.services.boards.handover_live import queue_handovers_changed
from app.services.boards.handover_similar import bud_key


async def notify_origin_card(
    db: AsyncSession, org_id: uuid.UUID, bud: BUDDocument, *, actor_id: uuid.UUID | None
) -> None:
    """Record and announce the BUD's delivery on its origin card, once per BUD."""
    if bud.status not in DELIVERED_STATUSES:
        return
    handovers = BoardHandoverRepository(db, org_id=org_id)
    row = await handovers.active_for_bud(bud.id)
    cards = BoardCardRepository(db, org_id=org_id)
    card = await cards.get_by_id(row.card_id) if row else None
    board = await BoardRepository(db, org_id=org_id).get_by_id(card.board_id) if card else None
    if card is None or board is None:
        return
    queue_handovers_changed(db, board.id, card.id)
    events = BoardCardEventRepository(db, org_id=org_id)
    # Serialises deliveries of the card's BUDs, so the last one sees the rest.
    await cards.lock(card)
    if await events.has_for_bud(card.id, BoardCardEventType.DELIVERED, bud.id):
        return
    key = bud_key(bud.bud_number)
    facts = {"bud_id": str(bud.id), "bud_key": key, "bud_status": bud.status.value}
    await record_event(db, card, BoardCardEventType.DELIVERED, actor_id=actor_id, detail=facts)
    if all_delivered(await handovers.active_bud_statuses(card.id)):
        await record_event(
            db, card, BoardCardEventType.FULLY_DELIVERED, actor_id=actor_id, detail=facts
        )
    notice = await handover_notices.stage_delivered(
        db, board, card, bud_key=key, actor_id=actor_id
    )
    if notice is not None:
        call_after_commit(db, notice.send)
