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

"""Editing a board's settings, and archiving or restoring it."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_enums import BoardStatus, BoardVisibility
from app.repositories.board import BoardRepository
from app.repositories.board_stage import BoardStageRepository
from app.schemas.boards.board import BoardDetail, BoardRead, BoardUpdate
from app.services.boards.access import BoardAccess
from app.services.boards.constants import HANDOVER_LANDING_STATUSES
from app.services.boards.errors import BOARD_TAKEN, BoardConflictError, BoardRuleError
from app.services.boards.live import BoardChanges, BoardSocketEvent
from app.services.boards.reads import board_detail
from app.services.boards.stage_rules import check_stages

# Settings that can be cleared with an explicit ``null``.
_NULLABLE = ("description", "handover_stage_id", "return_stage_id")
# Settings that are only ever replaced, never cleared.
_REPLACEABLE = ("visibility", "handover_enabled", "handover_target_status", "ai_enabled")


async def update_board(db: AsyncSession, access: BoardAccess, body: BoardUpdate) -> BoardDetail:
    """Apply the settings in ``body``; omitted fields stay as they are.

    The board's stages are locked before the board row is touched: card
    writes take a stage lock and then the board row (for numbering), so
    the same order here can't deadlock with them.
    """
    board, changes = access.board, BoardChanges(access.board.id)
    stages = await BoardStageRepository(db, org_id=access.org_id).lock_board_stages(board.id)
    repo = BoardRepository(db, org_id=access.org_id)
    sent = body.model_fields_set
    if body.name is not None and body.name != board.name:
        if await repo.key_or_name_taken(name=body.name, exclude=board.id):
            raise BoardConflictError(BOARD_TAKEN)
        board.name = body.name
    was_org_wide = board.visibility is BoardVisibility.ORG
    for field in _NULLABLE:
        if field in sent:
            setattr(board, field, getattr(body, field))
    for field in _REPLACEABLE:
        if getattr(body, field) is not None:
            setattr(board, field, getattr(body, field))
    if board.handover_target_status not in HANDOVER_LANDING_STATUSES:
        raise BoardRuleError("Handed-over cards can only land before development starts.")
    if board.handover_enabled and board.handover_stage_id is None:
        raise BoardRuleError("Pick the stage that hands cards over before turning handover on.")
    check_stages(
        stages, handover_stage_id=board.handover_stage_id, return_stage_id=board.return_stage_id
    )
    if not await repo.save(board):
        raise BoardConflictError(BOARD_TAKEN)
    if was_org_wide and board.visibility is BoardVisibility.MEMBERS:
        changes.recheck_access(None)
    changes.emit(BoardSocketEvent.BOARD_UPDATED, board=_board_json(access))
    await changes.commit(db)
    return await board_detail(db, access)


async def set_archived(db: AsyncSession, access: BoardAccess, *, archived: bool) -> BoardDetail:
    """Archive the board (nothing on it can change) or bring it back."""
    board = access.board
    target = BoardStatus.ARCHIVED if archived else BoardStatus.ACTIVE
    if board.status is not target:
        board.status = target
        await BoardRepository(db, org_id=access.org_id).save(board)
        changes = BoardChanges(board.id)
        changes.emit(BoardSocketEvent.BOARD_UPDATED, board=_board_json(access))
        await changes.commit(db)
    return await board_detail(db, access)


def _board_json(access: BoardAccess) -> dict[str, object]:
    return BoardRead.model_validate(access.board).model_dump(mode="json")
