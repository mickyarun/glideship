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

"""Looking after one's import sessions: listing open ones, discarding, back to review.

Who may touch a session is :func:`app.services.imports.sessions.get_session`'s
rule. Item maps outlive their session, so discarding a session or
reviewing it again never lets an imported item import twice onto a board.
"""

import uuid
from types import MappingProxyType
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.external_import import OPEN_IMPORT_STATUSES, ExternalImportStatus
from app.repositories.external_import import ExternalImportSessionRepository
from app.schemas.boards.imports import (
    ImportListStatus,
    ImportSessionList,
    ImportSessionRead,
    ImportSessionSummary,
)
from app.services.boards.access import BoardCaller
from app.services.boards.errors import BoardErrorCode, BoardStorageError
from app.services.imports.errors import ImportStateError
from app.services.imports.session_read import session_read
from app.services.imports.sessions import get_session
from app.services.imports.storage import delete_source_file

# A session no job is working on; pending and parsing ones have a job coming.
DISCARDABLE: Final = (
    ExternalImportStatus.READY,
    ExternalImportStatus.FAILED,
    ExternalImportStatus.COMPLETED,
)
LISTED_STATUSES: Final = MappingProxyType({ImportListStatus.OPEN: OPEN_IMPORT_STATUSES})
STILL_WORKING = "This import is still being read or running; discard it once it stops."
CANT_REVIEW = "Only an import that stopped after its board was read can be reviewed again."
FILE_NOT_REMOVED = "The uploaded file couldn't be removed; try discarding the import again."


async def list_mine(
    db: AsyncSession, caller: BoardCaller, state: ImportListStatus
) -> ImportSessionList:
    """The caller's own sessions in ``state``, newest first, at most the per-person cap."""
    repo = ExternalImportSessionRepository(db, org_id=caller.org_id)
    rows = await repo.list_for(
        caller.user_id, LISTED_STATUSES[state], settings.boards.import_max_open_per_user
    )
    return ImportSessionList(items=[ImportSessionSummary.model_validate(s) for s in rows])


async def discard(db: AsyncSession, caller: BoardCaller, session_id: uuid.UUID) -> None:
    """Delete a session no job is working on, with its uploaded file.

    Raises:
        ImportStateError: The session is pending, being read or running.
        BoardStorageError: Storage kept the file; the session stays.
    """
    session = await get_session(db, caller, session_id)
    path = session.storage_path
    repo = ExternalImportSessionRepository(db, org_id=caller.org_id)
    # Deleted before the file goes, so a start racing this one finds no session.
    if not await repo.delete_in(session.id, DISCARDABLE):
        raise ImportStateError(STILL_WORKING, code=BoardErrorCode.IMPORT_STILL_WORKING)
    if path and not await delete_source_file(path):
        await db.rollback()
        raise BoardStorageError(FILE_NOT_REMOVED)
    await db.commit()


async def back_to_review(
    db: AsyncSession, caller: BoardCaller, session_id: uuid.UUID
) -> ImportSessionRead:
    """Reopen the mapping of a session that failed after its board was read.

    It becomes ``ready`` with its saved mapping, so the mapping can be saved
    again (say, after a mapped stage was deleted) and the import started; a
    start resumes, skipping what earlier runs imported.
    """
    session = await get_session(db, caller, session_id)
    repo = ExternalImportSessionRepository(db, org_id=caller.org_id)
    reopened = session.discovery is not None and await repo.claim(
        session.id,
        from_statuses=(ExternalImportStatus.FAILED,),
        to_status=ExternalImportStatus.READY,
        job_id=None,
    )
    if not reopened:
        raise ImportStateError(CANT_REVIEW)
    await db.commit()
    await db.refresh(session)
    return await session_read(db, session)
