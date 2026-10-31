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

"""Import sessions as the API sees them: reading one, queueing its jobs, starting it.

A session is visible to the person who started it, and to holders of
``boards:manage``; anyone else, and every other org, gets 404.
"""

import asyncio
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions_boards import BOARDS_MANAGE
from app.models.external_import import ExternalImportSession, ExternalImportStatus, ImportMode
from app.repositories.board import BoardRepository
from app.repositories.external_import import ExternalImportSessionRepository
from app.schemas.boards.import_mapping import ImportMapping
from app.schemas.boards.imports import ImportAccepted, ImportResult, ImportSessionRead
from app.schemas.boards.trello_discovery import TrelloDiscovery
from app.services.boards.access import BoardCaller
from app.services.imports.errors import ImportNotFoundError, ImportStateError
from app.services.imports.pipeline import ImportJobPayload
from app.services.imports.target import (
    check_may_create,
    importer_access,
    session_mapping,
)
from app.services.imports.trello.credentials import load_credentials
from app.services.job_queue import JOB_IMPORT_DISCOVER, JOB_IMPORT_RUN, create_job_with_id

QUEUE_FULL = "Too many imports are queued right now. Try again in a minute."
CANT_START = "This import can only start once it's reviewed, or again after it failed."
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


async def session_read(db: AsyncSession, session: ExternalImportSession) -> ImportSessionRead:
    """The session with its discovery, mapping and result parsed."""
    board_key = None
    if session.board_id is not None:
        board = await BoardRepository(db, org_id=session.org_id).get_by_id(session.board_id)
        board_key = board.key if board else None
    return ImportSessionRead(
        id=session.id,
        source_kind=session.source_kind,
        mode=session.mode,
        status=session.status,
        board_id=session.board_id,
        board_key=board_key,
        total_cards=session.total_cards,
        processed_count=session.processed_count,
        last_processed_index=session.last_processed_index,
        job_id=session.job_id,
        error=session.error,
        discovery=None
        if session.discovery is None
        else TrelloDiscovery.model_validate(session.discovery),
        mapping=None if session.config is None else ImportMapping.model_validate(session.config),
        result=None if session.result is None else ImportResult.model_validate(session.result),
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


async def queue_job(
    db: AsyncSession,
    caller: BoardCaller,
    session: ExternalImportSession,
    *,
    job_type: str,
    from_statuses: tuple[ExternalImportStatus, ...],
    to_status: ExternalImportStatus,
) -> ImportAccepted:
    """Move the session to ``to_status`` with a fresh job id, commit, then enqueue.

    The row is committed first so the job always finds it; if the queue
    is full the session is marked failed and the caller can try again.
    """
    job_id = str(uuid.uuid4())
    repo = ExternalImportSessionRepository(db, org_id=caller.org_id)
    if not await repo.claim(
        session.id, from_statuses=from_statuses, to_status=to_status, job_id=job_id
    ):
        raise ImportStateError(CANT_START)
    await db.commit()
    payload = ImportJobPayload(org_id=caller.org_id, session_id=session.id, user_id=caller.user_id)
    try:
        create_job_with_id(
            job_id, job_type, payload=payload.model_dump(mode="json"), user_id=str(caller.user_id)
        )
    except asyncio.QueueFull as exc:
        await repo.claim(
            session.id,
            from_statuses=(to_status,),
            to_status=ExternalImportStatus.FAILED,
            job_id=None,
        )
        await db.commit()
        raise ImportStateError(QUEUE_FULL) from exc
    return ImportAccepted(job_id=job_id, session_id=session.id)


async def queue_discovery(
    db: AsyncSession, caller: BoardCaller, session: ExternalImportSession
) -> ImportAccepted:
    """Queue the parse job for a session just created as pending."""
    return await queue_job(
        db,
        caller,
        session,
        job_type=JOB_IMPORT_DISCOVER,
        from_statuses=(ExternalImportStatus.PENDING,),
        to_status=ExternalImportStatus.PARSING,
    )


async def start_import(
    db: AsyncSession, caller: BoardCaller, session_id: uuid.UUID
) -> ImportAccepted:
    """Queue the import job: first run, or a resume after a failure."""
    session = await get_session(db, caller, session_id)
    if session.status not in STARTABLE or session.discovery is None:
        raise ImportStateError(CANT_START)
    session_mapping(session)
    if session.board_id is None:
        check_may_create(caller)
    else:
        board = await BoardRepository(db, org_id=caller.org_id).get_by_id(session.board_id)
        if board is None:
            raise ImportStateError(CANT_START)
        await importer_access(db, caller, board.key)
    if session.mode is ImportMode.API:
        await load_credentials(db, caller.org_id)
    return await queue_job(
        db,
        caller,
        session,
        job_type=JOB_IMPORT_RUN,
        from_statuses=STARTABLE,
        to_status=ExternalImportStatus.RUNNING,
    )
