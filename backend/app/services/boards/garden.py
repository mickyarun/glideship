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


"""What the Garden hears about board work, on ``board_activity:<org_id>``, after the commit.

Three things, as ambience only (no XP): a card reaching a ``done`` stage,
a card handed over to Delivery, and one of a card's BUDs delivered. They
come from the card's history as it is written
(:func:`app.services.boards.events.record_event`), so every path that
moves, hands over or delivers a card is covered, and imports (which record
``imported``) stay quiet. The topic reaches the whole org's Garden, so an
event names only its kind and actor; the board and card keys are added
only when the board is visible to the whole org.
"""

import uuid
from enum import StrEnum
from typing import Any, Final

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board import BoardStage
from app.models.board_card import BoardCard
from app.models.board_enums import (
    BoardCardEventType,
    BoardStageCategory,
    BoardVisibility,
)
from app.repositories.board import BoardRepository
from app.services.after_commit import publish_after_commit
from app.services.boards.reads import card_key

BOARD_ACTIVITY_TOPIC: Final = "board_activity"
# Events that put a card in a stage it entered by itself.
_STAGE_ENTRIES: Final = frozenset(
    {BoardCardEventType.CREATED, BoardCardEventType.MOVED, BoardCardEventType.MOVED_BOARD}
)


class BoardActivityKind(StrEnum):
    """What happened, as the Garden shows it."""

    CARD_DONE = "card_done"
    HANDOVER = "handover"
    BUD_DELIVERED = "bud_delivered"


def board_activity_topic(org_id: uuid.UUID) -> str:
    """The org-wide Garden topic for board activity."""
    return f"{BOARD_ACTIVITY_TOPIC}:{org_id}"


def activity_kind(
    event_type: BoardCardEventType, from_stage: BoardStage | None, to_stage: BoardStage | None
) -> BoardActivityKind | None:
    """The Garden activity a card event is, if any."""
    if event_type is BoardCardEventType.HANDED_OVER:
        return BoardActivityKind.HANDOVER
    if event_type is BoardCardEventType.DELIVERED:
        return BoardActivityKind.BUD_DELIVERED
    done = BoardStageCategory.DONE
    entered_done = to_stage is not None and to_stage.category is done
    from_done = from_stage is not None and from_stage.category is done
    if event_type in _STAGE_ENTRIES and entered_done and not from_done:
        return BoardActivityKind.CARD_DONE
    return None


async def note_card_event(
    db: AsyncSession,
    card: BoardCard,
    event_type: BoardCardEventType,
    *,
    actor_id: uuid.UUID | None,
    from_stage: BoardStage | None,
    to_stage: BoardStage | None,
) -> None:
    """Queue the Garden event for a card event, to go out when ``db`` commits."""
    kind = activity_kind(event_type, from_stage, to_stage)
    if kind is None:
        return
    board = await BoardRepository(db, org_id=card.org_id).get_by_id(card.board_id)
    if board is None:
        return
    payload: dict[str, Any] = {
        "kind": kind.value,
        "actor_id": None if actor_id is None else str(actor_id),
    }
    if board.visibility is BoardVisibility.ORG:
        payload["board_key"] = board.key
        payload["card_key"] = card_key(board.key, card.number)
    publish_after_commit(db, board_activity_topic(card.org_id), payload)
