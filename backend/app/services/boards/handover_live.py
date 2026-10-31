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

"""Tell open boards that a handed-over BUD changed, so their chips refresh.

Called wherever a BUD's status changes (the shared status change, restore,
the delivered hook). It queues ``card_handovers_changed {card_id}`` on the
board of every card holding a handover of the BUD, sent once the change
commits; the same message queued twice in one transaction goes out once.
A failure here is logged and never stops the status change.
"""

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.board_handover import BoardHandoverRepository
from app.services.after_commit import publish_after_commit_once
from app.services.boards.live import BoardSocketEvent, board_topic

logger = structlog.get_logger(__name__)


def queue_handovers_changed(db: AsyncSession, board_id: uuid.UUID, card_id: uuid.UUID) -> None:
    """Queue ``card_handovers_changed`` for one card, sent after the commit."""
    message = {
        "event": BoardSocketEvent.CARD_HANDOVERS_CHANGED.value,
        "actor_id": None,
        "origin": None,
        "card_id": str(card_id),
    }
    publish_after_commit_once(db, board_topic(board_id), message)


async def queue_origin_card_refresh(
    db: AsyncSession, org_id: uuid.UUID, bud_id: uuid.UUID
) -> None:
    """Queue ``card_handovers_changed`` for each card holding a handover of the BUD."""
    # One read, without autoflush, so the caller's writes flush when they
    # always have; no SAVEPOINT for the same reason (it would flush first).
    try:
        with db.no_autoflush:
            cards = await BoardHandoverRepository(db, org_id=org_id).cards_for_bud(bud_id)
    except Exception:
        logger.exception("origin_card_refresh_failed", bud_id=str(bud_id))
        return
    for board_id, card_id in cards:
        queue_handovers_changed(db, board_id, card_id)
