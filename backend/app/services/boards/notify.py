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

:func:`recheck_after_discard` runs when a BUD is discarded (on the dev side
or by a send-back): a discarded BUD no longer counts toward its card's
delivery, so a card whose other live BUDs all reached prod becomes fully
delivered then.
"""

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_card import BoardCard
from app.models.board_enums import BoardCardEventType
from app.models.bud import BUDDocument, BUDStatus
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

logger = structlog.get_logger(__name__)


async def _origin_card(
    db: AsyncSession, org_id: uuid.UUID, bud: BUDDocument
) -> tuple[uuid.UUID, BoardCard] | None:
    """The board id and card holding the BUD's live handover, locked; None without one."""
    row = await BoardHandoverRepository(db, org_id=org_id).active_for_bud(bud.id)
    cards = BoardCardRepository(db, org_id=org_id)
    card = await cards.get_by_id(row.card_id) if row else None
    if card is None:
        return None
    queue_handovers_changed(db, card.board_id, card.id)
    # Serialises deliveries of the card's BUDs, so the last one sees the rest.
    await cards.lock(card)
    return card.board_id, card


async def recheck_after_discard(
    db: AsyncSession, org_id: uuid.UUID, bud: BUDDocument, *, actor_id: uuid.UUID | None
) -> None:
    """Mark the origin card fully delivered if, without this BUD, every live one is.

    Called as the BUD is being discarded (before its status is written), in
    a SAVEPOINT: a failure is logged and never stops the discard.
    """
    try:
        async with db.begin_nested():
            await _fully_delivered_without(db, org_id, bud, actor_id=actor_id)
    except Exception:
        logger.exception("origin_card_discard_recheck_failed", bud_id=str(bud.id))


async def _fully_delivered_without(
    db: AsyncSession, org_id: uuid.UUID, bud: BUDDocument, *, actor_id: uuid.UUID | None
) -> None:
    origin = await _origin_card(db, org_id, bud)
    if origin is None:
        return
    card = origin[1]
    events = BoardCardEventRepository(db, org_id=org_id)
    if await events.has_for_bud(card.id, BoardCardEventType.FULLY_DELIVERED, bud.id):
        return
    handovers = BoardHandoverRepository(db, org_id=org_id)
    if all_delivered(await handovers.active_bud_statuses(card.id, excluding=bud.id)):
        facts = {
            "bud_id": str(bud.id),
            "bud_key": bud_key(bud.bud_number),
            "bud_status": BUDStatus.DISCARDED.value,
        }
        await record_event(
            db, card, BoardCardEventType.FULLY_DELIVERED, actor_id=actor_id, detail=facts
        )


async def notify_origin_card(
    db: AsyncSession, org_id: uuid.UUID, bud: BUDDocument, *, actor_id: uuid.UUID | None
) -> None:
    """Record and announce the BUD's delivery on its origin card, once per BUD."""
    if bud.status not in DELIVERED_STATUSES:
        return
    origin = await _origin_card(db, org_id, bud)
    board = await BoardRepository(db, org_id=org_id).get_by_id(origin[0]) if origin else None
    if origin is None or board is None:
        return
    card = origin[1]
    handovers = BoardHandoverRepository(db, org_id=org_id)
    events = BoardCardEventRepository(db, org_id=org_id)
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
