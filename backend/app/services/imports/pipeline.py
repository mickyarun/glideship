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
a message for the person who started it, and a board that already exists
hears ``board_imported`` with that status. The run commits once per batch.
Every run walks all items from the first and the item maps skip what's
already on the board, so a restart (the job queue is in memory) resumes,
and cards that failed before get another try. A run that ends with failed
cards ends failed too, so it can be started again; one that ends with
none completes, and its source file is deleted.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.external_import import ExternalImportSession, ExternalImportStatus
from app.repositories.external_import import ExternalImportSessionRepository
from app.schemas.boards.imports import ImportResult
from app.schemas.jobs import JobState
from app.services.imports.batch import running_result, write_batch
from app.services.imports.board_plan import BoardPlan, build_plan
from app.services.imports.budget import run_budget
from app.services.imports.context import ImportContext
from app.services.imports.items import ExternalItem, import_items
from app.services.imports.job_payload import ImportJobPayload
from app.services.imports.outcome import fail_job, finish_run
from app.services.imports.registry import source_for
from app.services.imports.source import ImportSource
from app.services.imports.target import current_caller, session_mapping, target_access
from app.services.job_queue import update_job


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
    try:
        async with source_for(session.source_kind) as source:
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
        await fail_job(db, payload, job_id, exc)


async def run_import(db: AsyncSession, payload: ImportJobPayload, job_id: str) -> None:
    """Write every item not yet on the board, batch by batch, then announce one summary."""
    session = await _session(db, payload, ExternalImportStatus.RUNNING)
    if session is None:
        return
    update_job(job_id, state=JobState.RUNNING, status_message="Importing cards")
    try:
        async with source_for(session.source_kind) as source:
            caller = await current_caller(db, payload.org_id, payload.user_id)
            await source.check_startable(db, session, caller)
            board = await source.load(db, session)
            mapping = session_mapping(session)
            access = await target_access(db, session, caller)
            ctx = ImportContext(db, access, session, await run_budget(db, session))
            _restore(ctx)
            plan = await build_plan(ctx, mapping, board.labels)
            # The new board (if any), its stages, labels and people commit together.
            await db.commit()
            already = await _write_all(ctx, source, plan, import_items(board, mapping), job_id)
            await finish_run(ctx, await running_result(ctx, already), job_id)
    except Exception as exc:
        await fail_job(db, payload, job_id, exc)


def _restore(ctx: ImportContext) -> None:
    """Carry what earlier runs of the session counted for the cards they wrote."""
    earlier = ImportResult.model_validate(ctx.session.result or {})
    ctx.counters.update(earlier.dropped)
    ctx.suppressed = earlier.suppressed_events


async def _write_all(
    ctx: ImportContext,
    source: ImportSource,
    plan: BoardPlan,
    items: list[ExternalItem],
    job_id: str,
) -> int:
    size = settings.boards.import_batch_size
    already = 0
    for start in range(0, len(items), size):
        already = await write_batch(ctx, source, plan, items[start : start + size], already)
        _progress(job_id, ctx.session)
    return already


def _progress(job_id: str, session: ExternalImportSession) -> None:
    total = session.total_cards or 0
    pct = min(99, session.processed_count * 100 // total) if total else 0
    update_job(
        job_id, progress_pct=pct, status_message=f"Imported {session.processed_count} of {total}"
    )
