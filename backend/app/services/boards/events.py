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

"""Write a card's history, freezing the board and stage categories as they are now.

The board and both categories are copied onto the event, so metrics stay
right after the card changes board or a stage is re-categorised. Edits by
one person within ``BoardsConfig.edit_coalesce_seconds`` merge into the
first ``edited`` event of that window instead of adding a row each.
"""

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.board import BoardStage
from app.models.board_card import BoardCard
from app.models.board_card_detail import BoardCardEvent
from app.models.board_enums import BoardCardEventType
from app.repositories.board_access import BoardAccessRepository
from app.repositories.board_card_event import BoardCardEventRepository
from app.schemas.boards.card_detail import EventPage, EventRead
from app.services.boards.access import BoardAccess, CardAccess

# What a moved_board entry says about each board it names, blanked for
# readers who can't open that board (each key names its board too).
_HIDDEN: dict[str, dict[str, Any]] = {
    "from_board": {
        "from_board": None,
        "from_stage": None,
        "old_key": None,
        "dropped_labels": [],
        "cleared_repo": None,
    },
    "to_board": {"to_board": None, "new_key": None},
}


async def record_event(
    db: AsyncSession,
    card: BoardCard,
    event_type: BoardCardEventType,
    *,
    actor_id: uuid.UUID | None,
    from_stage: BoardStage | None = None,
    to_stage: BoardStage | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """Add one event to the card's history."""
    await BoardCardEventRepository(db, org_id=card.org_id).add(
        BoardCardEvent(
            org_id=card.org_id,
            card_id=card.id,
            board_id=card.board_id,
            type=event_type,
            actor_id=actor_id,
            from_stage_id=from_stage.id if from_stage else None,
            to_stage_id=to_stage.id if to_stage else None,
            from_category=from_stage.category if from_stage else None,
            to_category=to_stage.category if to_stage else None,
            detail=detail or {},
        )
    )


async def record_edit(
    db: AsyncSession, card: BoardCard, *, actor_id: uuid.UUID, fields: list[str], now: datetime
) -> None:
    """Record that ``fields`` changed, merging into the actor's recent edit if any."""
    if not fields:
        return
    since = now - timedelta(seconds=settings.boards.edit_coalesce_seconds)
    repo = BoardCardEventRepository(db, org_id=card.org_id)
    recent = await repo.latest_edit(card.id, actor_id, since)
    if recent is None:
        await record_event(
            db, card, BoardCardEventType.EDITED, actor_id=actor_id, detail={"fields": fields}
        )
        return
    merged = sorted({*recent.detail.get("fields", []), *fields})
    # A new dict, so the JSONB column is seen as changed.
    recent.detail = {**recent.detail, "fields": merged}


async def list_events(
    db: AsyncSession, target: CardAccess, *, before: uuid.UUID | None, limit: int | None
) -> EventPage:
    """A page of the card's history, newest first."""
    size = limit or settings.boards.events_page_size
    repo = BoardCardEventRepository(db, org_id=target.access.org_id)
    rows = await repo.page(target.card.id, before=before, limit=size + 1)
    page = rows[:size]
    items = [EventRead.model_validate(r) for r in page]
    return EventPage(
        items=await _hide_unseen_boards(db, target.access, items),
        next_before=page[-1].id if len(rows) > size else None,
    )


def _named_boards(event: EventRead) -> dict[str, uuid.UUID]:
    """The boards a ``moved_board`` entry names, by the detail field naming each."""
    if event.type is not BoardCardEventType.MOVED_BOARD:
        return {}
    named: dict[str, uuid.UUID] = {}
    for side in _HIDDEN:
        ref = event.detail.get(side)
        raw = ref.get("id") if isinstance(ref, dict) else None
        try:
            named[side] = uuid.UUID(str(raw))
        except ValueError:
            continue
    return named


async def _hide_unseen_boards(
    db: AsyncSession, access: BoardAccess, items: list[EventRead]
) -> list[EventRead]:
    """Blank what a ``moved_board`` entry says about a board the reader can't open.

    Either side: a source's name, key, stage, labels and repository, or a
    target's name and the key the card took there, stay with people who
    can see that board; everyone else reads "another board". One role
    lookup for the whole page.
    """
    named = [_named_boards(item) for item in items]
    boards = {board for sides in named for board in sides.values()}
    seen = await BoardAccessRepository(db, org_id=access.org_id).boards_with_role(
        boards, access.user_id, access.perms
    )
    out: list[EventRead] = []
    for item, sides in zip(items, named, strict=True):
        hidden = [side for side, board in sides.items() if board not in seen]
        if not hidden:
            out.append(item)
            continue
        blank = {k: v for side in hidden for k, v in _HIDDEN[side].items()}
        out.append(item.model_copy(update={"detail": {**item.detail, **blank}}))
    return out
