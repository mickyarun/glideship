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

"""Editing a card's fields, assignees and labels."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_card import BoardCard
from app.models.board_enums import BoardCardEventType
from app.repositories.board_card import BoardCardRepository
from app.repositories.board_card_links import BoardCardLinkRepository
from app.schemas.boards.card import CardDetail, CardUpdate
from app.services.boards.access import CardAccess
from app.services.boards.card_checks import (
    check_assignees,
    check_dates,
    check_labels,
    check_open,
    check_repo,
)
from app.services.boards.errors import BoardRuleError
from app.services.boards.events import record_edit, record_event
from app.services.boards.live import BoardChanges, BoardSocketEvent
from app.services.boards.reads import card_detail, summary_json

# Plain fields a PATCH can set; ``title`` and ``due_done`` can't be null.
_FIELDS = ("title", "description_md", "priority", "start_at", "due_at", "due_done", "repo_id")
_REQUIRED = frozenset({"title", "due_done"})


async def update_card(db: AsyncSession, target: CardAccess, body: CardUpdate) -> CardDetail:
    """Apply the edits in ``body`` and record them in the card's history.

    Edits never check the stage's required fields; those apply on entry.
    """
    access, card = target.access, target.card
    if "repo_id" in body.model_fields_set:
        await check_repo(db, access, body.repo_id)
    # Held so two edits can't both add the same assignee or label.
    await BoardCardRepository(db, org_id=access.org_id).lock(card)
    check_open(card)
    edited = _apply_fields(card, body)
    check_dates(card.start_at, card.due_at)
    links = BoardCardLinkRepository(db, org_id=access.org_id)
    if body.label_ids is not None:
        await check_labels(db, access, body.label_ids)
        added, removed = await links.set_labels(card, body.label_ids)
        if added or removed:
            edited.append("labels")
    if body.assignee_ids is not None:
        # Only new assignees need access; someone who since lost it can stay
        # on the card until they're removed.
        current = await links.assignee_ids(card.id)
        await check_assignees(db, access, set(body.assignee_ids) - current)
        added, removed = await links.set_assignees(card, body.assignee_ids)
        await _record_people(db, card, access.user_id, BoardCardEventType.ASSIGNED, added)
        await _record_people(db, card, access.user_id, BoardCardEventType.UNASSIGNED, removed)
    await record_edit(db, card, actor_id=access.user_id, fields=edited, now=datetime.now(UTC))
    detail = await card_detail(db, access.board, card)
    changes = BoardChanges.of(access)
    changes.emit(BoardSocketEvent.CARD_UPDATED, card=summary_json(detail))
    await changes.commit(db)
    return detail


def _apply_fields(card: BoardCard, body: CardUpdate) -> list[str]:
    edited: list[str] = []
    for field in _FIELDS:
        if field not in body.model_fields_set:
            continue
        value = getattr(body, field)
        if value is None and field in _REQUIRED:
            raise BoardRuleError(f"{field} can't be empty.")
        if getattr(card, field) != value:
            setattr(card, field, value)
            edited.append(field)
    return edited


async def _record_people(
    db: AsyncSession,
    card: BoardCard,
    actor_id: uuid.UUID,
    event_type: BoardCardEventType,
    user_ids: set[uuid.UUID],
) -> None:
    if user_ids:
        await record_event(
            db,
            card,
            event_type,
            actor_id=actor_id,
            detail={"user_ids": sorted(str(u) for u in user_ids)},
        )
