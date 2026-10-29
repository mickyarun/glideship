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

"""Adding, editing, reordering and deleting a board's stages.

Every change locks the board's stage rows, applies itself in memory, and
checks the whole set against :mod:`app.services.boards.stage_rules`
before anything is flushed.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.board import BoardStage
from app.repositories.board_card_event import BoardCardEventRepository
from app.repositories.board_card_position import BoardCardPositionRepository
from app.repositories.board_stage import BoardStageRepository
from app.schemas.boards.stage import StageCreate, StageOrder, StageRead, StageUpdate
from app.services.boards.access import BoardAccess
from app.services.boards.errors import BoardConflictError, BoardItemNotFoundError, BoardRuleError
from app.services.boards.live import BoardChanges, BoardSocketEvent
from app.services.boards.stage_rules import check_stage_count, check_stages

STAGE_NOT_FOUND = "Stage not found."
STAGE_NAME_TAKEN = "Another stage on this board already has that name."


def _check(access: BoardAccess, stages: list[BoardStage]) -> None:
    board = access.board
    check_stages(
        stages, handover_stage_id=board.handover_stage_id, return_stage_id=board.return_stage_id
    )


def _find(stages: list[BoardStage], stage_id: uuid.UUID) -> BoardStage:
    stage = next((s for s in stages if s.id == stage_id), None)
    if stage is None:
        raise BoardItemNotFoundError(STAGE_NOT_FOUND)
    return stage


def _make_default(stages: list[BoardStage], chosen: BoardStage) -> None:
    for stage in stages:
        stage.is_default = stage is chosen


async def _save(db: AsyncSession, access: BoardAccess, changes: BoardChanges) -> None:
    if not await BoardStageRepository(db, org_id=access.org_id).save():
        raise BoardConflictError(STAGE_NAME_TAKEN)
    changes.emit(BoardSocketEvent.STAGE_CHANGED)
    await changes.commit(db)


async def create_stage(db: AsyncSession, access: BoardAccess, body: StageCreate) -> StageRead:
    """A new stage at the right-hand end of the board."""
    repo = BoardStageRepository(db, org_id=access.org_id)
    stages = await repo.lock_board_stages(access.board.id)
    check_stage_count(len(stages) + 1)
    stage = BoardStage(
        org_id=access.org_id,
        board_id=access.board.id,
        name=body.name,
        category=body.category,
        position=max((s.position for s in stages), default=-1) + 1,
        wip_limit=body.wip_limit,
        is_default=False,
    )
    stages.append(stage)
    if body.is_default:
        _make_default(stages, stage)
    _check(access, stages)
    await repo.add(stage)
    await _save(db, access, BoardChanges(access.board.id))
    return StageRead.model_validate(stage)


async def update_stage(
    db: AsyncSession, access: BoardAccess, stage_id: uuid.UUID, body: StageUpdate
) -> StageRead:
    """Rename, re-categorise, set the WIP limit or make a stage the default.

    The default moves by naming a new one; un-setting the only default is refused.
    """
    stages = await BoardStageRepository(db, org_id=access.org_id).lock_board_stages(
        access.board.id
    )
    stage = _find(stages, stage_id)
    if body.name is not None:
        stage.name = body.name
    if body.category is not None:
        stage.category = body.category
    if "wip_limit" in body.model_fields_set:
        stage.wip_limit = body.wip_limit
    if body.is_default:
        _make_default(stages, stage)
    elif body.is_default is False and stage.is_default:
        raise BoardRuleError("Make another stage the default instead.")
    _check(access, stages)
    await _save(db, access, BoardChanges(access.board.id))
    return StageRead.model_validate(stage)


async def reorder_stages(
    db: AsyncSession, access: BoardAccess, body: StageOrder
) -> list[StageRead]:
    """Put the board's stages in the given order; every stage must be listed once."""
    stages = await BoardStageRepository(db, org_id=access.org_id).lock_board_stages(
        access.board.id
    )
    if sorted(body.stage_ids) != sorted(s.id for s in stages):
        raise BoardRuleError("List every stage of this board exactly once.")
    by_id = {s.id: s for s in stages}
    for position, stage_id in enumerate(body.stage_ids):
        by_id[stage_id].position = position
    changes = BoardChanges(access.board.id)
    await _save(db, access, changes)
    return [StageRead.model_validate(by_id[i]) for i in body.stage_ids]


async def delete_stage(
    db: AsyncSession, access: BoardAccess, stage_id: uuid.UUID, move_to: uuid.UUID | None
) -> None:
    """Delete a stage, moving its cards to the bottom of ``move_to`` first."""
    board = access.board
    repo = BoardStageRepository(db, org_id=access.org_id)
    stages = await repo.lock_board_stages(board.id)
    stage = _find(stages, stage_id)
    if stage_id in (board.handover_stage_id, board.return_stage_id):
        raise BoardConflictError("This stage is used for handover; change that setting first.")
    if stage.is_default:
        raise BoardRuleError("Make another stage the default before deleting this one.")
    remaining = [s for s in stages if s.id != stage_id]
    _check(access, remaining)
    target = None if move_to is None else _find(remaining, move_to)
    if target is not None:
        await _move_cards(db, access, stage, target)
    elif await BoardCardPositionRepository(db, org_id=access.org_id).has_cards(stage.id):
        raise BoardRuleError("Choose the stage this stage's cards should move to.")
    await repo.delete(stage)
    changes = BoardChanges(board.id)
    changes.emit(BoardSocketEvent.STAGE_CHANGED)
    if target is not None:
        changes.emit(BoardSocketEvent.STAGE_REORDERED, stage_id=str(target.id))
    await changes.commit(db)


async def _move_cards(
    db: AsyncSession, access: BoardAccess, source: BoardStage, target: BoardStage
) -> None:
    await BoardCardEventRepository(db, org_id=access.org_id).record_stage_moves(
        source.id,
        target.id,
        board_id=access.board.id,
        actor_id=access.user_id,
        from_category=source.category,
        to_category=target.category,
    )
    positions = BoardCardPositionRepository(db, org_id=access.org_id)
    await positions.move_all(
        source.id,
        target.id,
        target.category,
        start=await positions.last_position(target.id) or 0.0,
        gap=settings.boards.position_gap,
        now=datetime.now(UTC),
    )
