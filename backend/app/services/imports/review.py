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


"""Checking and saving the review screen's mapping for a parsed import, for any source.

Every source group is mapped exactly once (a new stage, an existing stage,
or skipped); members map only to people who can open the target board; the
target is a new board checked like ``POST /boards`` or an existing board
the caller is admin on. The source says which ids its discovery holds.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions_boards import BOARDS_VIEW
from app.models.board import Board
from app.models.external_import import ExternalImportSession, ExternalImportStatus
from app.repositories.board_access import BoardAccessRepository
from app.repositories.board_stage import BoardStageRepository
from app.repositories.import_people import ImportPeopleRepository
from app.schemas.boards.import_mapping import ImportMapping, NewBoardTarget, StageChoice
from app.services.boards.access import BoardCaller
from app.services.boards.board_create import check_new_board
from app.services.boards.errors import BoardRuleError
from app.services.boards.stage_rules import check_stage_count
from app.services.imports.errors import ImportStateError, StageNameTakenError
from app.services.imports.registry import source_for
from app.services.imports.source import MappingIds
from app.services.imports.stage_plan import planned_stages, stage_key
from app.services.imports.target import check_may_create, importer_access

NOT_READY = "This import can only be reviewed once it's parsed and before it starts."
EVERY_GROUP = "Map every list exactly once: to a new stage, an existing stage, or skip."
UNKNOWN_MEMBER = "The mapping names a member the imported board doesn't have."
NO_ACCESS = "Some of the people you mapped can't open the target board."
STAGE_NOT_ON_BOARD = "An existing stage in the mapping isn't on the target board."
NEW_BOARD_EXISTING = "A new board has no existing stages to map lists into."


async def save_mapping(
    db: AsyncSession, caller: BoardCaller, session: ExternalImportSession, body: ImportMapping
) -> None:
    """Check ``body`` against the parsed source and the target, then store it."""
    if session.status is not ExternalImportStatus.READY or session.discovery is None:
        raise ImportStateError(NOT_READY)
    _check_ids(body, source_for(session.source_kind).mapping_ids(session.discovery))
    people = set(body.user_for().values())
    target = body.target
    board_id: uuid.UUID | None = None
    if isinstance(target, NewBoardTarget):
        check_may_create(caller)
        key = await check_new_board(db, caller, key=target.key, name=target.name)
        body = body.model_copy(update={"target": target.model_copy(update={"key": key})})
        if any(entry.action is StageChoice.EXISTING for entry in body.groups):
            raise BoardRuleError(NEW_BOARD_EXISTING)
        planned_stages(body, new_board=True)
        repo = ImportPeopleRepository(db, org_id=caller.org_id)
        allowed = await repo.active_holding(people, BOARDS_VIEW)
    else:
        board = (await importer_access(db, caller, target.key)).board
        await _check_existing_stages(db, board, body)
        access = BoardAccessRepository(db, org_id=caller.org_id)
        allowed = await access.users_with_access(board.id, people)
        board_id = board.id
    if people - allowed:
        raise BoardRuleError(NO_ACCESS)
    session.config = body.model_dump(mode="json")
    session.board_id = board_id
    await db.commit()
    await db.refresh(session)


def _check_ids(body: ImportMapping, known: MappingIds) -> None:
    mapped = [entry.group_id for entry in body.groups]
    if len(mapped) != len(set(mapped)) or set(mapped) != known.groups:
        raise BoardRuleError(EVERY_GROUP)
    if not {m.member_id for m in body.members} <= known.members:
        raise BoardRuleError(UNKNOWN_MEMBER)


async def _check_existing_stages(db: AsyncSession, board: Board, body: ImportMapping) -> None:
    stages = await BoardStageRepository(db, org_id=board.org_id).list_for_board(board.id)
    ids = {s.id for s in stages}
    if any(e.action is StageChoice.EXISTING and e.stage_id not in ids for e in body.groups):
        raise BoardRuleError(STAGE_NOT_ON_BOARD)
    names = {stage_key(s.name) for s in stages}
    planned = planned_stages(body, new_board=False)
    for entry in body.groups:
        if entry.action is StageChoice.NEW and entry.name and stage_key(entry.name) in names:
            raise StageNameTakenError(group_id=entry.group_id, stage_name=entry.name)
    check_stage_count(len(stages) + len(planned))
