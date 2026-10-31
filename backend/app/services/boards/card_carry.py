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

"""What a card keeps when it moves to another board, and which stage it lands in.

Labels are matched by name (ignoring case) on the target board, and the
rest are dropped. Assignees who can't edit the target board are removed.
A repository stays only when the target board links it.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board import BoardStage
from app.models.board_card import BoardCard
from app.repositories.board_access import BoardAccessRepository
from app.repositories.board_card_links import BoardCardLinkRepository
from app.repositories.board_label import BoardLabelRepository
from app.services.boards.access import BoardAccess
from app.services.boards.constants import BOARD_ACTION_MIN_ROLE, BoardAction
from app.services.boards.errors import BoardItemNotFoundError
from app.services.boards.stage_service import STAGE_NOT_FOUND


@dataclass(frozen=True)
class Carry:
    """The labels and assignees a moving card keeps, and what it loses."""

    label_ids: list[uuid.UUID]
    dropped_labels: list[str]
    assignee_ids: list[uuid.UUID]
    removed_assignees: list[uuid.UUID]


def pick_stage(
    stages: Sequence[BoardStage], from_stage: BoardStage, stage_id: uuid.UUID | None
) -> BoardStage:
    """``stage_id`` on the target, else the same name, same category, then the default.

    Raises:
        BoardItemNotFoundError: ``stage_id`` isn't a stage of the target board.
    """
    if stage_id is not None:
        chosen = next((s for s in stages if s.id == stage_id), None)
        if chosen is None:
            raise BoardItemNotFoundError(STAGE_NOT_FOUND)
        return chosen
    name = from_stage.name.casefold()
    for match in (
        lambda s: s.name.casefold() == name,
        lambda s: s.category is from_stage.category,
        lambda s: s.is_default,
    ):
        found = next((s for s in stages if match(s)), None)
        if found is not None:
            return found
    if not stages:
        raise BoardItemNotFoundError(STAGE_NOT_FOUND)
    return stages[0]


async def carry_over(
    db: AsyncSession, source: BoardAccess, target: BoardAccess, card: BoardCard
) -> Carry:
    """Match the card's labels on the target board and keep its assignees who can edit there."""
    org = source.org_id
    links = BoardCardLinkRepository(db, org_id=org)
    labels = BoardLabelRepository(db, org_id=org)
    mine = await links.label_ids(card.id)
    names = [lb.name for lb in await labels.list_for_board(source.board.id) if lb.id in mine]
    by_name: dict[str, uuid.UUID] = {}
    for label in await labels.list_for_board(target.board.id):
        by_name.setdefault(label.name.casefold(), label.id)
    kept = [by_name[n.casefold()] for n in names if n.casefold() in by_name]
    dropped = [n for n in names if n.casefold() not in by_name]
    people = await links.assignee_ids(card.id)
    editors = await BoardAccessRepository(db, org_id=org).users_with_access(
        target.board.id, people, min_role=BOARD_ACTION_MIN_ROLE[BoardAction.EDIT_CARD]
    )
    return Carry(
        label_ids=sorted(set(kept)),
        dropped_labels=dropped,
        assignee_ids=sorted(editors),
        removed_assignees=sorted(people - editors),
    )
