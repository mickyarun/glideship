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

"""A card's checklist: add, edit, tick, reorder and remove lines.

Each change announces the card's new summary, since the board shows the
checklist count on the card.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.board_card_detail import BoardCardChecklistItem
from app.repositories.board_card import BoardCardRepository
from app.repositories.board_card_checklist import BoardCardChecklistRepository
from app.schemas.boards.card_detail import (
    ChecklistItemCreate,
    ChecklistItemRead,
    ChecklistItemUpdate,
    ChecklistOrder,
)
from app.services.boards.access import CardAccess
from app.services.boards.card_checks import check_open
from app.services.boards.constants import CHECKLIST_MAX_ITEMS
from app.services.boards.errors import BoardConflictError, BoardItemNotFoundError, BoardRuleError
from app.services.boards.live import BoardChanges, BoardSocketEvent
from app.services.boards.reads import card_detail, summary_json


async def list_items(db: AsyncSession, target: CardAccess) -> list[ChecklistItemRead]:
    """The card's checklist, top to bottom."""
    repo = BoardCardChecklistRepository(db, org_id=target.access.org_id)
    return [ChecklistItemRead.model_validate(i) for i in await repo.list_for_card(target.card.id)]


async def add_item(
    db: AsyncSession, target: CardAccess, body: ChecklistItemCreate
) -> ChecklistItemRead:
    """A new line at the bottom of the checklist."""
    await BoardCardRepository(db, org_id=target.access.org_id).lock(target.card)
    check_open(target.card)
    repo = BoardCardChecklistRepository(db, org_id=target.access.org_id)
    if await repo.count_for_card(target.card.id) >= CHECKLIST_MAX_ITEMS:
        raise BoardConflictError(f"A checklist holds at most {CHECKLIST_MAX_ITEMS} items.")
    last = await repo.last_position(target.card.id)
    item = BoardCardChecklistItem(
        org_id=target.access.org_id,
        card_id=target.card.id,
        text=body.text,
        group_name=body.group_name,
        position=(last or 0.0) + settings.boards.position_gap,
    )
    await repo.create(item)
    await _announce(db, target)
    return ChecklistItemRead.model_validate(item)


async def update_item(
    db: AsyncSession, target: CardAccess, item_id: uuid.UUID, body: ChecklistItemUpdate
) -> ChecklistItemRead:
    """Edit a line's text or group, or tick it."""
    check_open(target.card)
    item = await _get(db, target, item_id)
    if body.text is not None:
        item.text = body.text
    if body.done is not None:
        item.done = body.done
    if "group_name" in body.model_fields_set:
        item.group_name = body.group_name
    await _announce(db, target)
    return ChecklistItemRead.model_validate(item)


async def reorder_items(
    db: AsyncSession, target: CardAccess, body: ChecklistOrder
) -> list[ChecklistItemRead]:
    """Put the checklist in the given order; every line must be listed once."""
    check_open(target.card)
    repo = BoardCardChecklistRepository(db, org_id=target.access.org_id)
    items = {i.id: i for i in await repo.list_for_card(target.card.id)}
    if sorted(body.item_ids) != sorted(items):
        raise BoardRuleError("List every checklist item of this card exactly once.")
    for rank, item_id in enumerate(body.item_ids, start=1):
        items[item_id].position = rank * settings.boards.position_gap
    await _announce(db, target)
    return [ChecklistItemRead.model_validate(items[i]) for i in body.item_ids]


async def delete_item(db: AsyncSession, target: CardAccess, item_id: uuid.UUID) -> None:
    """Remove a line."""
    check_open(target.card)
    item = await _get(db, target, item_id)
    await BoardCardChecklistRepository(db, org_id=target.access.org_id).delete(item)
    await _announce(db, target)


async def _get(db: AsyncSession, target: CardAccess, item_id: uuid.UUID) -> BoardCardChecklistItem:
    repo = BoardCardChecklistRepository(db, org_id=target.access.org_id)
    item = await repo.get_in_card(target.card.id, item_id)
    if item is None:
        raise BoardItemNotFoundError("Checklist item not found.")
    return item


async def _announce(db: AsyncSession, target: CardAccess) -> None:
    """Commit and announce the card's new checklist counts."""
    detail = await card_detail(db, target.access.board, target.card)
    changes = BoardChanges.of(target.access)
    changes.emit(BoardSocketEvent.CARD_UPDATED, card=summary_json(detail))
    await changes.commit(db)
