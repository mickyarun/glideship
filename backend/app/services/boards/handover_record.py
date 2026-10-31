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

"""What a handover confirm writes and announces about the card, inside its transaction."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_enums import BoardCardEventType, BoardHandoverStatus
from app.models.board_handover import BoardCardHandover
from app.repositories.board_handover import BoardHandoverRepository, HandoverRow
from app.repositories.board_handover_keys import BoardHandoverKeyRepository
from app.schemas.boards.card import CardDetail
from app.schemas.boards.handover import HandoverConfirm, HandoverMode
from app.services.boards.access import CardAccess
from app.services.boards.events import record_event
from app.services.boards.handover_bud import HandedOverBUD
from app.services.boards.handover_card_stage import CardStage
from app.services.boards.handover_reads import handover_read, live_handover
from app.services.boards.handover_rehandover import reactivate
from app.services.boards.handover_similar import bud_key
from app.services.boards.live import BoardChanges, BoardSocketEvent
from app.services.boards.reads import summary_json


async def record(
    db: AsyncSession,
    target: CardAccess,
    body: HandoverConfirm,
    result: HandedOverBUD,
    stage: CardStage,
    reused: BoardCardHandover | None,
) -> BoardCardHandover:
    """Insert the handover row (or reactivate the reused one), its key, a ``handed_over`` event."""
    access, card, bud = target.access, target.card, result.bud
    linked = body.mode is HandoverMode.LINK
    handovers = BoardHandoverRepository(db, org_id=access.org_id)
    if reused is not None:
        row = reactivate(reused, access.user_id, bud.status, body.idempotency_key)
        await db.flush()
    else:
        row = await handovers.add(
            BoardCardHandover(
                org_id=access.org_id,
                card_id=card.id,
                bud_id=bud.id,
                status=BoardHandoverStatus.ACTIVE,
                linked_existing=linked,
                target_status=None if linked else bud.status,
                handed_over_by=access.user_id,
                handed_over_at=datetime.now(UTC),
                idempotency_key=body.idempotency_key,
            )
        )
    await BoardHandoverKeyRepository(db, org_id=access.org_id).add(
        card.id, body.idempotency_key, row.id
    )
    await record_event(
        db,
        card,
        BoardCardEventType.HANDED_OVER,
        actor_id=access.user_id,
        from_stage=stage.from_stage if stage.moved else None,
        to_stage=stage.to_stage,
        detail={
            "bud_id": str(bud.id),
            "bud_key": bud_key(bud.bud_number),
            "mode": body.mode.value,
            "bud_status": bud.status.value,
            **({"again": True} if reused is not None else {}),
        },
    )
    return row


async def announce(
    db: AsyncSession, target: CardAccess, stage: CardStage, row: HandoverRow, detail: CardDetail
) -> None:
    """Queue the board's events (ids, keys and statuses only), then commit."""
    access, card = target.access, target.card
    changes = BoardChanges.of(access)
    if stage.rebalanced and stage.to_stage is not None:
        changes.emit(BoardSocketEvent.STAGE_REORDERED, stage_id=str(stage.to_stage.id))
    if stage.moved:
        changes.emit(
            BoardSocketEvent.CARD_MOVED,
            card=summary_json(detail),
            from_stage_id=str(stage.from_stage.id),
        )
    read = handover_read(row, can_open_bud=False)
    changes.emit(
        BoardSocketEvent.CARD_HANDED_OVER, card_id=str(card.id), handover=live_handover(read)
    )
    await changes.commit(db)
