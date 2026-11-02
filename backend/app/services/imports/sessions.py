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


"""Import sessions as the API sees them: reading one, and starting it.

A session is visible to the person who started it, and to holders of
``boards:manage``; anyone else, and every other org, gets 404.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions_boards import BOARDS_MANAGE
from app.models.external_import import ExternalImportSession, ExternalImportStatus
from app.repositories.board_stage import BoardStageRepository
from app.repositories.external_import import ExternalImportSessionRepository
from app.schemas.boards.imports import ImportAccepted
from app.services.boards.access import BoardCaller
from app.services.imports.errors import ImportNotFoundError, ImportStateError
from app.services.imports.queueing import CANT_START, queue_discovery, queue_job
from app.services.imports.registry import source_for
from app.services.imports.stage_plan import check_mapped_stages
from app.services.imports.target import (
    check_may_import,
    check_new_target,
    session_mapping,
    target_board_access,
)
from app.services.job_queue import JOB_IMPORT_RUN

STARTABLE = (ExternalImportStatus.READY, ExternalImportStatus.FAILED)


async def get_session(
    db: AsyncSession, caller: BoardCaller, session_id: uuid.UUID
) -> ExternalImportSession:
    """The caller's session (any of the org's with ``boards:manage``)."""
    repo = ExternalImportSessionRepository(db, org_id=caller.org_id)
    session = await repo.get_for(
        session_id, caller.user_id, any_creator=caller.perms.has(BOARDS_MANAGE)
    )
    if session is None:
        raise ImportNotFoundError()
    return session


async def start_import(
    db: AsyncSession, caller: BoardCaller, session_id: uuid.UUID
) -> ImportAccepted:
    """Queue the next job: the import (first run, or a resume), or the parse again.

    A session that failed before its board was read (a restart mid-parse,
    a full queue) goes back to parsing; one that was read runs the import.
    """
    session = await get_session(db, caller, session_id)
    if session.status not in STARTABLE:
        raise ImportStateError(CANT_START)
    await check_may_import(db, caller)
    await source_for(session.source_kind).check_startable(db, session, caller)
    if session.discovery is None:
        if session.status is not ExternalImportStatus.FAILED:
            raise ImportStateError(CANT_START)
        return await queue_discovery(
            db, caller, session, from_statuses=(ExternalImportStatus.FAILED,)
        )
    mapping = session_mapping(session)
    if session.board_id is None:
        await check_new_target(db, caller, mapping)
    else:
        board = (await target_board_access(db, session, caller)).board
        stages = await BoardStageRepository(db, org_id=caller.org_id).list_for_board(board.id)
        check_mapped_stages(mapping, (s.id for s in stages))
    return await queue_job(
        db,
        caller,
        session,
        job_type=JOB_IMPORT_RUN,
        from_statuses=STARTABLE,
        to_status=ExternalImportStatus.RUNNING,
    )
