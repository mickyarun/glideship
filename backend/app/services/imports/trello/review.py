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

"""Checking and saving the review screen's mapping for a parsed Trello board.

Every list is mapped exactly once (a new stage, an existing stage, or
skipped); members map only to people who can open the target board; the
target is a new board checked like ``POST /boards`` or an existing board
the caller is admin on.
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
from app.schemas.boards.trello_discovery import TrelloDiscovery
from app.services.boards.access import BoardCaller
from app.services.boards.board_service import check_new_board
from app.services.boards.errors import BoardConflictError, BoardRuleError
from app.services.boards.stage_rules import check_stage_count
from app.services.imports.errors import ImportStateError
from app.services.imports.stage_plan import planned_stages, stage_key
from app.services.imports.target import check_may_create, importer_access

NOT_READY = "This import can only be reviewed once it's parsed and before it starts."
EVERY_LIST = "Map every Trello list exactly once: to a new stage, an existing stage, or skip."
UNKNOWN_MEMBER = "The mapping names a Trello member this board doesn't have."
NO_ACCESS = "Some of the people you mapped can't open the target board."
STAGE_NOT_ON_BOARD = "An existing stage in the mapping isn't on the target board."
STAGE_NAME_TAKEN = "The target board already has a stage called {name!r}; map the list to it."
NEW_BOARD_EXISTING = "A new board has no existing stages to map lists into."


async def save_mapping(
    db: AsyncSession, caller: BoardCaller, session: ExternalImportSession, body: ImportMapping
) -> None:
    """Check ``body`` against the parsed board and the target, then store it."""
    if session.status is not ExternalImportStatus.READY or session.discovery is None:
        raise ImportStateError(NOT_READY)
    _check_ids(body, TrelloDiscovery.model_validate(session.discovery))
    people = set(body.user_for().values())
    target = body.target
    board_id: uuid.UUID | None = None
    if isinstance(target, NewBoardTarget):
        check_may_create(caller)
        key = await check_new_board(db, caller, key=target.key, name=target.name)
        body = body.model_copy(update={"target": target.model_copy(update={"key": key})})
        if any(entry.action is StageChoice.EXISTING for entry in body.lists):
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


def _check_ids(body: ImportMapping, discovery: TrelloDiscovery) -> None:
    mapped = [entry.list_id for entry in body.lists]
    if len(mapped) != len(set(mapped)) or set(mapped) != {lst.id for lst in discovery.lists}:
        raise BoardRuleError(EVERY_LIST)
    if not {m.member_id for m in body.members} <= {m.id for m in discovery.members}:
        raise BoardRuleError(UNKNOWN_MEMBER)


async def _check_existing_stages(db: AsyncSession, board: Board, body: ImportMapping) -> None:
    stages = await BoardStageRepository(db, org_id=board.org_id).list_for_board(board.id)
    ids = {s.id for s in stages}
    if any(e.action is StageChoice.EXISTING and e.stage_id not in ids for e in body.lists):
        raise BoardRuleError(STAGE_NOT_ON_BOARD)
    names = {stage_key(s.name) for s in stages}
    planned = planned_stages(body, new_board=False)
    for plan in planned:
        if stage_key(plan.name) in names:
            raise BoardConflictError(STAGE_NAME_TAKEN.format(name=plan.name))
    check_stage_count(len(stages) + len(planned))
