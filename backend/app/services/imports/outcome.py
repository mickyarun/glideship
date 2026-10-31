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


"""How an import job ends: completed, failed with some cards, or stopped by an error.

A clean run completes and deletes its source file (kept for the retention
sweep if storage refuses). A run with failed cards ends failed, so it can
be started again to retry them. Either way, and when an error stops a job
on a board that exists, the board hears one board_imported with the
status.
"""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.external_import import ExternalImportStatus
from app.repositories.external_import import ExternalImportSessionRepository
from app.schemas.boards.imports import ImportResult
from app.schemas.jobs import JobState
from app.services.boards.errors import BoardError
from app.services.boards.live import BoardChanges, BoardSocketEvent
from app.services.imports.context import ImportContext
from app.services.imports.job_payload import ImportJobPayload
from app.services.imports.storage import delete_source_file
from app.services.job_queue import update_job

logger = structlog.get_logger(__name__)

UNEXPECTED = "The import stopped unexpectedly. Start it again to resume."
PARTIAL = "{n} cards couldn't be imported. Start the import again to retry them."


async def finish_run(ctx: ImportContext, result: ImportResult, job_id: str) -> None:
    """End a run that wrote every batch: completed, or failed when some cards failed."""
    session = ctx.session
    session.result = result.model_dump(mode="json")
    source_file = session.storage_path
    if result.failed:
        session.status = ExternalImportStatus.FAILED
        session.error = PARTIAL.format(n=result.failed)
    else:
        session.status = ExternalImportStatus.COMPLETED
        session.storage_path = None
    summary = {"session_id": str(session.id), "status": session.status.value, **session.result}
    await ctx.finish(summary)
    completed = session.status is ExternalImportStatus.COMPLETED
    if completed and source_file and not await delete_source_file(source_file):
        # Keep the path so the retention sweep tries again.
        session.storage_path = source_file
        await ctx.db.commit()
    if session.error:
        update_job(job_id, state=JobState.FAILED, error=session.error, result=summary)
    else:
        update_job(job_id, state=JobState.COMPLETED, progress_pct=100, result=summary)


async def fail_job(
    db: AsyncSession, payload: ImportJobPayload, job_id: str, exc: Exception
) -> None:
    """Mark the session failed after exc, telling its board when it has one."""
    reason = str(exc) if isinstance(exc, BoardError) else UNEXPECTED
    logger.warning(
        "import_failed",
        session_id=str(payload.session_id),
        error=str(exc),
        exc_info=not isinstance(exc, BoardError),
    )
    await db.rollback()
    repo = ExternalImportSessionRepository(db, org_id=payload.org_id)
    session = await repo.get_by_id(payload.session_id)
    if session is not None:
        session.status = ExternalImportStatus.FAILED
        session.error = reason
        changes = BoardChanges(session.board_id, payload.user_id) if session.board_id else None
        if changes is not None:
            changes.emit(
                BoardSocketEvent.BOARD_IMPORTED,
                session_id=str(session.id),
                status=session.status.value,
                error=reason,
            )
            await changes.commit(db)
        else:
            await db.commit()
    update_job(job_id, state=JobState.FAILED, error=reason)
