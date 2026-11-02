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

"""A board's labels: names are unique per board, colours come from the theme."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board import BoardLabel
from app.repositories.board_label import BoardLabelRepository
from app.schemas.boards.label import LabelCreate, LabelRead, LabelUpdate
from app.services.boards.access import BoardAccess
from app.services.boards.errors import BoardConflictError, BoardItemNotFoundError
from app.services.boards.live import BoardChanges, BoardSocketEvent

LABEL_TAKEN = "This board already has a label with that name."


async def list_labels(db: AsyncSession, access: BoardAccess) -> list[LabelRead]:
    """The board's labels, by name."""
    labels = await BoardLabelRepository(db, org_id=access.org_id).list_for_board(access.board.id)
    return [LabelRead.model_validate(label) for label in labels]


async def create_label(db: AsyncSession, access: BoardAccess, body: LabelCreate) -> LabelRead:
    """A new label on the board."""
    label = BoardLabel(
        org_id=access.org_id, board_id=access.board.id, name=body.name, color=body.color
    )
    return await _save(db, access, label)


async def update_label(
    db: AsyncSession, access: BoardAccess, label_id: uuid.UUID, body: LabelUpdate
) -> LabelRead:
    """Rename or recolour a label."""
    label = await _get(db, access, label_id)
    if body.name is not None:
        label.name = body.name
    if body.color is not None:
        label.color = body.color
    return await _save(db, access, label)


async def delete_label(db: AsyncSession, access: BoardAccess, label_id: uuid.UUID) -> None:
    """Delete a label; cards carrying it lose it."""
    label = await _get(db, access, label_id)
    await BoardLabelRepository(db, org_id=access.org_id).delete(label)
    changes = BoardChanges.of(access)
    changes.emit(BoardSocketEvent.LABEL_CHANGED, label_id=str(label_id), deleted=True)
    await changes.commit(db)


async def _get(db: AsyncSession, access: BoardAccess, label_id: uuid.UUID) -> BoardLabel:
    repo = BoardLabelRepository(db, org_id=access.org_id)
    label = await repo.get_in_board(access.board.id, label_id)
    if label is None:
        raise BoardItemNotFoundError("Label not found.")
    return label


async def _save(db: AsyncSession, access: BoardAccess, label: BoardLabel) -> LabelRead:
    if not await BoardLabelRepository(db, org_id=access.org_id).save(label):
        raise BoardConflictError(LABEL_TAKEN)
    read = LabelRead.model_validate(label)
    changes = BoardChanges.of(access)
    changes.emit(BoardSocketEvent.LABEL_CHANGED, label=read.model_dump(mode="json"))
    await changes.commit(db)
    return read
