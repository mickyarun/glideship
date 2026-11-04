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

"""The AI draft sweeper: claims pending drafts and finishes them.

Runs every minute with limited concurrency. A draft is never lost to a
restart, because the queue is the rows. Permanent errors (no provider,
refused login, a provider that can't run without tools) set the row to
``none`` and the person sees the manual view; anything else retries three
times, then ``failed``. A result only ever fills the AI columns, so it
can't touch what anyone wrote, however late it arrives.
"""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.appraisal import Appraisal
from app.models.appraisal_ai_run import AppraisalAiRun
from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_enums import DraftKind, DraftStatus
from app.repositories.appraisal_drafts import claim_check_ins, claim_summaries
from app.repositories.organization import OrganizationRepository
from app.services.appraisals import crypto
from app.services.appraisals.draft_check import DraftUnreadableError, as_stored, checked_lines
from app.services.appraisals.draft_inputs import DraftInput, check_in_input, summary_input
from app.services.appraisals.draft_runner import PERMANENT, run_draft
from app.services.claude_runner import ClaudeRunResult
from app.services.scheduling.tick_loop import run_tick_loop

logger = structlog.get_logger(__name__)
TICK_SECONDS = 60
BATCH = 10
CONCURRENCY = 3
MAX_ATTEMPTS = 3
STALE_AFTER = timedelta(minutes=15)
UNREADABLE = "unreadable"
NO_CITED_LINES = "no_cited_lines"

Row = AppraisalCheckIn | Appraisal


@dataclass(frozen=True)
class Slot:
    """Which columns a kind of draft lives in, and how to build its input."""

    kind: DraftKind
    model: type[Row]
    status: str
    attempts: str
    error: str
    claimed: str
    text: str
    build: Callable[[AsyncSession, Any], Awaitable[DraftInput | None]]


CHECK_IN = Slot(
    DraftKind.CHECK_IN,
    AppraisalCheckIn,
    "draft_status",
    "draft_attempts",
    "draft_error",
    "draft_claimed_at",
    "ai_summary",
    check_in_input,
)
SUMMARY = Slot(
    DraftKind.PERIOD_SUMMARY,
    Appraisal,
    "period_summary_status",
    "summary_attempts",
    "summary_error",
    "summary_claimed_at",
    "ai_period_summary",
    summary_input,
)


def after_failure(attempts: int, *, permanent: bool) -> DraftStatus:
    """Where a draft goes after a failed run (pure)."""
    if permanent:
        return DraftStatus.NONE
    return DraftStatus.FAILED if attempts >= MAX_ATTEMPTS else DraftStatus.PENDING


def _save(
    slot: Slot, row: Row, data: DraftInput, result: ClaudeRunResult, now: datetime
) -> str | None:
    """Apply a run's result to the row; the error code, if it failed."""
    code = str(result.error_code.value) if result.error_code else "unknown"
    permanent = result.error_code in PERMANENT
    lines = []
    if result.success:
        try:
            lines = checked_lines(result.output, data.sections, data.known_ids, data.limit)
            code = "" if lines else NO_CITED_LINES
        except DraftUnreadableError:
            code = UNREADABLE
    setattr(row, slot.claimed, None)
    if lines:
        crypto.seal_json(row, slot.text, as_stored(lines))
        setattr(row, slot.status, DraftStatus.READY)
        setattr(row, slot.error, None)
        if isinstance(row, AppraisalCheckIn):
            row.ai_generated_at = now
        return None
    attempts = getattr(row, slot.attempts)
    setattr(row, slot.status, after_failure(attempts, permanent=permanent))
    setattr(row, slot.error, code)
    return code


async def _load(db: AsyncSession, slot: Slot, record_id: uuid.UUID) -> Row | None:
    return cast(Row | None, await db.get(slot.model, record_id))


async def process(slot: Slot, record_id: uuid.UUID, now: datetime) -> None:
    """Build, run and save one claimed draft."""
    async with AsyncSessionLocal() as db:
        row = await _load(db, slot, record_id)
        if row is None:
            return
        org_id, profile_id = row.org_id, row.profile_id
        if getattr(row, slot.attempts) > MAX_ATTEMPTS:
            # Earlier tries died before saving anything; stop taking it.
            setattr(row, slot.status, DraftStatus.FAILED)
            setattr(row, slot.claimed, None)
            await db.commit()
            return
        data = await slot.build(db, row)
        if data is None:
            setattr(row, slot.status, DraftStatus.NONE)
            setattr(row, slot.claimed, None)
            await db.commit()
            return
        org = await OrganizationRepository(db).get_by_id(org_id)
        provider = org.ai_provider.value if org else "unknown"
    result = await run_draft(org_id, data.prompt)
    async with AsyncSessionLocal() as db:
        row = await _load(db, slot, record_id)
        if row is None:
            return
        code = _save(slot, row, data, result, now)
        if code is None and isinstance(row, AppraisalCheckIn):
            row.ai_model = provider
        run = AppraisalAiRun(
            org_id=org_id,
            profile_id=profile_id,
            kind=slot.kind,
            record_id=record_id,
            provider=provider,
            fact_ids=sorted(data.known_ids),
            error=code,
        )
        crypto.seal(run, "prompt", data.prompt)
        crypto.seal(run, "output", result.output)
        db.add(run)
        await db.commit()


async def _guarded(
    limit: asyncio.Semaphore, slot: Slot, record_id: uuid.UUID, now: datetime
) -> None:
    async with limit:
        try:
            await process(slot, record_id, now)
        except Exception:
            # Stays claimed; the stale check takes it again, up to the attempt limit.
            logger.exception("appraisal_draft_failed", kind=slot.kind.value, id=str(record_id))


async def tick_once(now_utc: datetime | None = None) -> None:
    """Claim a batch of each kind and run them."""
    now = now_utc or datetime.now(UTC)
    stale = now - STALE_AFTER
    async with AsyncSessionLocal() as db:
        check_ins = await claim_check_ins(db, now, stale, BATCH)
        summaries = await claim_summaries(db, now, stale, BATCH)
        await db.commit()
    limit = asyncio.Semaphore(CONCURRENCY)
    await asyncio.gather(
        *(_guarded(limit, CHECK_IN, i, now) for i in check_ins),
        *(_guarded(limit, SUMMARY, i, now) for i in summaries),
    )


async def run_draft_sweeper() -> None:
    """The long-running loop started from the app's lifespan."""
    await run_tick_loop("appraisal_draft_sweeper", TICK_SECONDS, tick_once)
