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

"""Send a BUD back to the card it was handed over from, before development starts.

One transaction, locking the BUD first (as every BUD-side writer does),
then the card (:mod:`handover_return_card`):

- the BUD is discarded through :func:`app.services.bud_discard.discard_bud`
  (feature inactive, ``status_change``, a version) and gets a
  ``returned_to_board`` timeline event;
- the handover row becomes ``returned`` with the reason;
- the card gets the reason as a comment by the person sending it back
  (with its ``commented`` event), and a ``returned`` event; with no other
  live handover left it moves to the board's return stage;
- the card's assignees get an in-app row and a DM (``board_handovers``).

The board hears ``card_moved`` (when it moved), ``card_activity`` (the
comment) and ``card_handover_returned`` after the commit. None of them,
nor the card events, carries the BUD's title.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_enums import BoardCardEventType, BoardHandoverStatus
from app.models.board_handover import BoardCardHandover
from app.models.bud import BUDDocument, BUDStatus, BUDTimelineEventType
from app.repositories.board_handover import BoardHandoverRepository, HandoverBUD
from app.repositories.bud import BUDRepository
from app.schemas.boards.handover import HandoverRead
from app.services.boards import handover_notices
from app.services.boards.card_notify import send
from app.services.boards.constants import HANDOVER_LANDING_STATUSES
from app.services.boards.errors import BoardItemNotFoundError
from app.services.boards.events import record_event
from app.services.boards.handover_reads import handover_read
from app.services.boards.handover_return_card import (
    ReturnCard,
    ReturnMove,
    lock_card,
    move_to_return_stage,
    post_reason,
)
from app.services.boards.handover_return_rules import (
    BUDPastReturnError,
    HandoverNotActiveError,
    discarded_on_dev_side,
)
from app.services.boards.handover_similar import bud_key
from app.services.boards.live import BoardChanges, BoardSocketEvent
from app.services.boards.reads import card_detail, card_key, summary_json
from app.services.bud_discard import discard_bud
from app.services.bud_timeline import record_event as record_bud_event

BUD_NOT_FOUND = "BUD not found."


async def return_to_board(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    bud_id: uuid.UUID,
    actor_id: uuid.UUID,
    actor_name: str | None,
    reason: str,
) -> HandoverRead:
    """Send the BUD back; the handover as it now is. Commits.

    Raises:
        BoardItemNotFoundError: No such BUD in the org.
        HandoverNotActiveError: The BUD has no live origin card.
        BUDPastReturnError: Development has started (or the BUD is closed).
        BoardConflictError: The card moved while it was being locked; retry.
    """
    buds = BUDRepository(db, org_id=org_id)
    bud = await buds.get_by_id(bud_id) if await buds.lock_for_edit(bud_id) else None
    if bud is None:
        raise BoardItemNotFoundError(BUD_NOT_FOUND)
    row = await BoardHandoverRepository(db, org_id=org_id).active_for_bud(bud.id)
    if row is None:
        raise HandoverNotActiveError()
    key = bud_key(bud.bud_number)
    if bud.status is BUDStatus.DISCARDED:
        raise discarded_on_dev_side(key)
    if bud.status not in HANDOVER_LANDING_STATUSES:
        raise BUDPastReturnError(bud.status)
    locked = await lock_card(db, org_id, row.card_id)
    await discard_bud(db, org_id, bud, actor_id=actor_id, actor_name=actor_name)
    await record_bud_event(
        db,
        org_id,
        bud.id,
        BUDTimelineEventType.RETURNED_TO_BOARD.value,
        actor_id=actor_id,
        actor_name=actor_name,
        detail={
            "board_id": str(locked.board.id),
            "card_id": str(locked.card.id),
            "card_key": card_key(locked.board.key, locked.card.number),
            "reason": reason,
        },
    )
    _mark_returned(row, actor_id, reason)
    moved = await _card_side(db, locked, row, key, actor_id, reason)
    notice = await handover_notices.stage_returned(
        db, locked.board, locked.card, bud_key=key, actor_id=actor_id, reason=reason
    )
    # A BUD route: the caller is working on the BUD, so the title is theirs to see.
    read = handover_read(
        (row, HandoverBUD(bud.bud_number, bud.title, bud.status)), can_open_bud=True
    )
    await _announce(db, locked, moved, row, bud, actor_id)
    send(notice)
    return read


def _mark_returned(row: BoardCardHandover, actor_id: uuid.UUID, reason: str) -> None:
    row.status = BoardHandoverStatus.RETURNED
    row.returned_by = actor_id
    row.returned_at = datetime.now(UTC)
    row.return_reason = reason


async def _card_side(
    db: AsyncSession,
    locked: ReturnCard,
    row: BoardCardHandover,
    key: str,
    actor_id: uuid.UUID,
    reason: str,
) -> ReturnMove:
    """The comment, the move when no live handover is left, and the ``returned`` event."""
    await db.flush()
    handovers = BoardHandoverRepository(db, org_id=row.org_id)
    alone = await handovers.count_live_for_card(locked.card.id) == 0
    moved = await move_to_return_stage(db, locked) if alone else ReturnMove(to_stage=None)
    comment = await post_reason(
        db, locked.card, author_id=actor_id, lead=f"Sent back from {key}: ", reason=reason
    )
    await record_event(
        db,
        locked.card,
        BoardCardEventType.RETURNED,
        actor_id=actor_id,
        from_stage=locked.from_stage if moved.to_stage else None,
        to_stage=moved.to_stage,
        detail={
            "bud_id": str(row.bud_id),
            "bud_key": key,
            "comment_id": str(comment.id),
            "reason": reason,
        },
    )
    return moved


async def _announce(
    db: AsyncSession,
    locked: ReturnCard,
    moved: ReturnMove,
    row: BoardCardHandover,
    bud: BUDDocument,
    actor_id: uuid.UUID,
) -> None:
    """Queue the board's events (ids, keys and statuses only), then commit."""
    changes = BoardChanges(locked.board.id, actor_id)
    if moved.rebalanced and moved.to_stage is not None:
        changes.emit(BoardSocketEvent.STAGE_REORDERED, stage_id=str(moved.to_stage.id))
    if moved.to_stage is not None:
        detail = await card_detail(db, locked.board, locked.card)
        changes.emit(
            BoardSocketEvent.CARD_MOVED,
            card=summary_json(detail),
            from_stage_id=str(locked.from_stage.id),
        )
    # The reason went up as a comment; open panels reload the thread.
    changes.emit(BoardSocketEvent.CARD_ACTIVITY, card_id=str(locked.card.id))
    changes.emit(
        BoardSocketEvent.CARD_HANDOVER_RETURNED,
        card_id=str(locked.card.id),
        handover={
            "id": str(row.id),
            "bud_id": str(bud.id),
            "bud_key": bud_key(bud.bud_number),
            "bud_status": BUDStatus.DISCARDED.value,
            "status": row.status.value,
        },
    )
    await changes.commit(db)
