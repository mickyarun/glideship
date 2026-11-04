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

Each minute a few workers take drafts one at a time until none is waiting,
so a draft asked for now starts as soon as a worker is free, and orgs take
turns. Nothing is lost to a restart, because the queue is the rows.
Permanent errors (no provider, refused login, a provider that can't run
without tools) set the row to ``none`` and the person sees the manual
view; anything else keeps its claim until it goes stale, which spaces the
retries out, and after three tries is ``failed``. A result only ever fills
the AI columns, so it can't touch what anyone wrote, however late it
arrives.
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.appraisal_ai_run import AppraisalAiRun
from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_enums import DraftStatus
from app.repositories.appraisal_drafts import Claim, claim_next
from app.repositories.organization import OrganizationRepository
from app.services.appraisals import crypto
from app.services.appraisals.draft_result import (
    CHECK_IN,
    MAX_ATTEMPTS,
    SUMMARY,
    Row,
    Slot,
    save_result,
)
from app.services.appraisals.draft_runner import run_draft, sweep_leftovers
from app.services.scheduling.tick_loop import run_tick_loop

logger = structlog.get_logger(__name__)
TICK_SECONDS = 60
WORKERS = 3
# Longer than the slowest run (Ollama's timeout is four times the usual one),
# so a live run is never taken twice; also the wait between retries.
STALE_AFTER = timedelta(minutes=30)
CRASHED = "crashed"


async def _load(db: AsyncSession, slot: Slot, record_id: uuid.UUID) -> Row | None:
    return cast(Row | None, await db.get(slot.model, record_id))


async def process(slot: Slot, claim: Claim) -> None:
    """Build, run and save one claimed draft."""
    record_id = claim.record_id
    async with AsyncSessionLocal() as db:
        row = await _load(db, slot, record_id)
        if row is None:
            return
        org_id, profile_id = row.org_id, row.profile_id
        if getattr(row, slot.attempts) > MAX_ATTEMPTS:
            # Earlier tries died before saving anything; stop taking it.
            setattr(row, slot.status, DraftStatus.FAILED)
            setattr(row, slot.error, CRASHED)
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
        # Someone else took it, or it was cancelled, while this one ran.
        if row is None or getattr(row, slot.claimed) != claim.claimed_at:
            return
        code = save_result(slot, row, data, result, claim.claimed_at)
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


async def _next(served: set[uuid.UUID], now: datetime) -> tuple[Slot, Claim] | None:
    """Claim one draft, giving each org a turn before any has a second."""
    stale = now - STALE_AFTER
    async with AsyncSessionLocal() as db:
        for slot in (CHECK_IN, SUMMARY):
            columns = (
                getattr(slot.model, slot.status),
                getattr(slot.model, slot.claimed),
                slot.attempts,
            )
            claim = await claim_next(db, slot.model, columns, now, stale, served)
            if claim is not None:
                await db.commit()
                if claim.org_id in served:
                    served.clear()
                served.add(claim.org_id)
                return slot, claim
    return None


async def _worker(served: set[uuid.UUID], now_utc: datetime | None) -> None:
    while (taken := await _next(served, now_utc or datetime.now(UTC))) is not None:
        slot, claim = taken
        try:
            await process(slot, claim)
        except Exception:
            # Keeps its claim; the stale check takes it again, up to the limit.
            logger.exception(
                "appraisal_draft_failed", kind=slot.kind.value, id=str(claim.record_id)
            )


async def tick_once(now_utc: datetime | None = None) -> None:
    """Work through every draft that's waiting."""
    served: set[uuid.UUID] = set()
    await asyncio.gather(*(_worker(served, now_utc) for _ in range(WORKERS)))


async def run_draft_sweeper() -> None:
    """The long-running loop started from the app's lifespan."""
    sweep_leftovers()
    await run_tick_loop("appraisal_draft_sweeper", TICK_SECONDS, tick_once)
