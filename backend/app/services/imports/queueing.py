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


"""Queueing an import's jobs: the session moves first, then the job is enqueued.

The row is committed before the job exists so the job always finds it.
When the in-memory queue is full, or the server is shutting down, the
session is marked failed (starting it again retries) and the caller gets
503 with a ``Retry-After``.
"""

import asyncio
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.external_import import ExternalImportSession, ExternalImportStatus
from app.repositories.external_import import ExternalImportSessionRepository
from app.schemas.boards.imports import ImportAccepted
from app.services.boards.access import BoardCaller
from app.services.boards.errors import BoardBusyError
from app.services.imports.errors import ImportStateError
from app.services.imports.job_payload import ImportJobPayload
from app.services.job_queue import JOB_IMPORT_DISCOVER, create_job_with_id

QUEUE_FULL = "Too many imports are queued right now. Try again in a minute."
CANT_START = "This import can only start once it's reviewed, or again after it failed."


async def queue_job(
    db: AsyncSession,
    caller: BoardCaller,
    session: ExternalImportSession,
    *,
    job_type: str,
    from_statuses: tuple[ExternalImportStatus, ...],
    to_status: ExternalImportStatus,
) -> ImportAccepted:
    """Move the session to ``to_status`` with a fresh job id, commit, then enqueue."""
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
    except (asyncio.QueueFull, RuntimeError) as exc:
        # RuntimeError: the queue is shutting down and takes no more jobs.
        await repo.claim(
            session.id,
            from_statuses=(to_status,),
            to_status=ExternalImportStatus.FAILED,
            job_id=None,
            error=QUEUE_FULL,
        )
        await db.commit()
        wait = settings.boards.import_busy_retry_after_seconds
        raise BoardBusyError(QUEUE_FULL, retry_after_seconds=wait) from exc
    return ImportAccepted(job_id=job_id, session_id=session.id)


async def queue_discovery(
    db: AsyncSession,
    caller: BoardCaller,
    session: ExternalImportSession,
    *,
    from_statuses: tuple[ExternalImportStatus, ...] = (ExternalImportStatus.PENDING,),
) -> ImportAccepted:
    """Queue the parse job: for a new session, or again for one whose parse failed."""
    return await queue_job(
        db,
        caller,
        session,
        job_type=JOB_IMPORT_DISCOVER,
        from_statuses=from_statuses,
        to_status=ExternalImportStatus.PARSING,
    )
