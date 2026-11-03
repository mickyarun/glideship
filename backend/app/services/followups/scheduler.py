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

"""Send each opted-in person their daily follow-ups at their own local time.

Ticks like the board due reminders: one read finds everyone who turned the
DM on, local times are worked out per person on every pass (so it's
DST-correct and catches up after a restart within the window), and only
orgs with someone due now get a session. Claims make it once per person
per local day however many ticks or backend instances run:
:mod:`app.services.followups.stage`.
"""

import asyncio
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.digest_claim import DigestClaimStatus
from app.repositories.digest_claim import DigestClaimRepository, settled_claims
from app.repositories.followup_settings import Subscriber
from app.repositories.followup_settings import followup_subscribers as subscribers
from app.services.followups.due_state import LocalDay
from app.services.followups.schedule import due_day
from app.services.followups.stage import KIND, stage_org
from app.services.notifications import NotificationCategory
from app.services.scheduling.claim_outcome import claim_outcome
from app.services.scheduling.pace import Pace
from app.services.scheduling.tick_loop import run_tick_loop
from app.services.slack_dm import send_each_rich

logger = structlog.get_logger(__name__)
CATEGORY = NotificationCategory.DAILY_FOLLOWUPS


async def tick_once(now_utc: datetime | None = None) -> None:
    """One pass over everyone who turned the follow-ups on."""
    now = now_utc or datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        people = await subscribers(db, CATEGORY.value)
        due = await _due_now(db, people, now)
    slots = asyncio.Semaphore(settings.followups.org_concurrency)

    async def _one(org_id: uuid.UUID, mine: dict[uuid.UUID, LocalDay]) -> None:
        async with slots:
            try:
                await org_pass(org_id, mine)
            except Exception:
                logger.exception("followups_org_failed", org_id=str(org_id))

    await asyncio.gather(*(_one(org_id, mine) for org_id, mine in due.items()))


async def _due_now(
    db: AsyncSession, people: list[Subscriber], now: datetime
) -> dict[uuid.UUID, dict[uuid.UUID, LocalDay]]:
    """Per org, the people whose follow-ups are due now and not already settled today."""
    days = {(p.org_id, p.user_id): local for p in people if (local := due_day(p, now))}
    cfg = settings.followups
    settled = await settled_claims(
        db,
        KIND,
        {user_id for _org, user_id in days},
        {local.day for local in days.values()},
        max_retries=cfg.max_retries,
        stale=timedelta(minutes=cfg.stale_minutes),
    )
    due: dict[uuid.UUID, dict[uuid.UUID, LocalDay]] = defaultdict(dict)
    for (org_id, user_id), local in days.items():
        if (org_id, user_id, local.day) not in settled:
            due[org_id][user_id] = local
    return due


async def org_pass(org_id: uuid.UUID, due: dict[uuid.UUID, LocalDay]) -> None:
    """Claim, compose and send the org's follow-ups for the people due now."""
    async with AsyncSessionLocal() as db:
        messages = await stage_org(db, org_id, due)
        await db.commit()
    if not messages:
        return
    cfg = settings.followups
    pace = Pace(cfg.dm_concurrency, cfg.dm_interval_seconds)
    payload = {user_id: (m.text, m.blocks) for user_id, m in messages.items()}
    reached = await send_each_rich(org_id, CATEGORY, payload, pace=pace)
    async with AsyncSessionLocal() as db:
        claims = DigestClaimRepository(db, org_id=org_id)
        for user_id in messages:
            status = claim_outcome(reached.get(user_id))
            error = "slack_failed" if status is DigestClaimStatus.FAILED else None
            await claims.finish(KIND, user_id, due[user_id].day, status, error)
        await db.commit()
    logger.info("followups_sent", org_id=str(org_id), people=len(messages), reached=len(reached))


async def run_forever() -> None:
    """Tick every ``FollowupsConfig.tick_seconds`` until cancelled."""
    await run_tick_loop("followups", settings.followups.tick_seconds, tick_once)
