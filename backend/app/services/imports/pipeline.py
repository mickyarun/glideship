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

"""The two import jobs, for every source: discover (parse) and run (write cards).

Both open their own database session, report progress with
``update_job`` and never raise: a failure marks the session failed with
a message for the person who started it. The run commits once per batch
together with ``last_processed_index``, so a restart (the job queue is in
memory) resumes after the last committed batch, and the item maps skip
anything already imported.
"""

import uuid
from typing import Any

import structlog
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.permission_deps import member_permission_set
from app.database import AsyncSessionLocal
from app.models.external_import import ExternalImportSession, ExternalImportStatus
from app.repositories.external_import import ExternalImportSessionRepository
from app.schemas.boards.imports import ImportResult
from app.schemas.jobs import JobState
from app.services.boards.access import BoardCaller
from app.services.boards.errors import BoardActionForbiddenError, BoardError
from app.services.imports.batch import write_batch
from app.services.imports.context import ImportContext
from app.services.imports.registry import source_for
from app.services.imports.source import ExternalItem, ImportSource
from app.services.imports.target import target_access
from app.services.job_queue import update_job

logger = structlog.get_logger(__name__)

UNEXPECTED = "The import stopped unexpectedly. Start it again to resume."
NOT_A_MEMBER = "The person who started this import is no longer in the organisation."


class ImportJobPayload(BaseModel):
    """What both import jobs carry."""

    org_id: uuid.UUID
    session_id: uuid.UUID
    user_id: uuid.UUID


async def handle_import_discover_job(job_id: str, raw: dict[str, Any]) -> None:
    """Job handler: parse (and in API mode fetch) the source, then wait for review."""
    async with AsyncSessionLocal() as db:
        await run_discovery(db, ImportJobPayload.model_validate(raw), job_id)


async def handle_import_run_job(job_id: str, raw: dict[str, Any]) -> None:
    """Job handler: write the reviewed import onto its board."""
    async with AsyncSessionLocal() as db:
        await run_import(db, ImportJobPayload.model_validate(raw), job_id)


async def _session(
    db: AsyncSession, payload: ImportJobPayload, status: ExternalImportStatus
) -> ExternalImportSession | None:
    repo = ExternalImportSessionRepository(db, org_id=payload.org_id)
    session = await repo.get_by_id(payload.session_id)
    return session if session is not None and session.status is status else None


async def run_discovery(db: AsyncSession, payload: ImportJobPayload, job_id: str) -> None:
    """Fill the session's discovery; it is then ready for review."""
    session = await _session(db, payload, ExternalImportStatus.PARSING)
    if session is None:
        return
    update_job(job_id, state=JobState.RUNNING, status_message="Reading the board")
    source = source_for(session.source_kind)
    try:
        found = await source.discover(db, session)
        session.discovery = found.summary
        session.total_cards = found.total_items
        session.status = ExternalImportStatus.READY
        await db.commit()
        update_job(
            job_id,
            state=JobState.COMPLETED,
            progress_pct=100,
            status_message="Ready to review",
            result={"sessionId": str(payload.session_id)},
        )
    except Exception as exc:
        await _fail(db, payload, job_id, exc)
    finally:
        await source.close()


async def run_import(db: AsyncSession, payload: ImportJobPayload, job_id: str) -> None:
    """Write every item not yet done, batch by batch, then announce one summary."""
    session = await _session(db, payload, ExternalImportStatus.RUNNING)
    if session is None:
        return
    update_job(job_id, state=JobState.RUNNING, status_message="Importing cards")
    source = source_for(session.source_kind)
    try:
        perms = await member_permission_set(db, payload.user_id, payload.org_id)
        if perms is None:
            raise BoardActionForbiddenError(NOT_A_MEMBER)
        caller = BoardCaller(user_id=payload.user_id, org_id=payload.org_id, perms=perms)
        ctx = ImportContext(db, await target_access(db, session, caller), session)
        await source.prepare(ctx)
        await db.commit()
        result = await _write_all(ctx, source, job_id)
        session.status = ExternalImportStatus.COMPLETED
        summary = {"session_id": str(session.id), **result.model_dump(mode="json")}
        await ctx.finish(summary)
        update_job(job_id, state=JobState.COMPLETED, progress_pct=100, result=summary)
    except Exception as exc:
        await _fail(db, payload, job_id, exc)
    finally:
        await source.close()


async def _write_all(ctx: ImportContext, source: ImportSource, job_id: str) -> ImportResult:
    session = ctx.session
    result = ImportResult.model_validate(session.result or {})
    ctx.counters.update(result.dropped)
    start = 0 if session.last_processed_index is None else session.last_processed_index + 1
    batch: list[ExternalItem] = []
    size = settings.boards.import_batch_size
    async for item in source.iter_items(session):
        if item.index < start:
            continue
        batch.append(item)
        if len(batch) >= size:
            result = await write_batch(ctx, source, batch, result)
            _progress(job_id, session)
            batch = []
    if batch:
        result = await write_batch(ctx, source, batch, result)
    return result


def _progress(job_id: str, session: ExternalImportSession) -> None:
    total = session.total_cards or 0
    pct = min(99, session.processed_count * 100 // total) if total else 0
    update_job(
        job_id, progress_pct=pct, status_message=f"Imported {session.processed_count} of {total}"
    )


async def _fail(db: AsyncSession, payload: ImportJobPayload, job_id: str, exc: Exception) -> None:
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
        await db.commit()
    update_job(job_id, state=JobState.FAILED, error=reason)
