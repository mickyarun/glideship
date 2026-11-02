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


"""Each morning, tell every assignee about their open cards due today or overdue.

Ticks like the leave digest: local times are recomputed every pass, so it's
DST-correct and catches up after a restart. The fire time is the org's
``boards.due_reminder_time`` (else ``BoardsConfig.due_reminder_default_time``)
in the leave digest's timezone, and reminders go out until
``due_reminder_window_minutes`` later on the same local date: down for less
than that, they go late the same day; down longer, the day is skipped.

Each tick reads the orgs with due cards once, works out which are in their
window from that one read, and only then opens a session per org, so an
org with old overdue cards costs nothing outside its window. Orgs send at
the same time (``due_reminder_org_concurrency``), each pacing its own DMs
(``due_reminder_dm_concurrency`` and ``due_reminder_dm_interval_seconds``)
so a large org stays inside Slack's rate limits and doesn't hold up the
rest. Claims and retries: :mod:`app.services.boards.due_stage`.
"""

import asyncio
from datetime import UTC, datetime, time, timedelta

import structlog

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.digest_claim import DigestClaimStatus
from app.repositories.board_due import DueOrg, orgs_with_due_cards
from app.repositories.digest_claim import DigestClaimRepository
from app.services.boards.due_stage import KIND, FireWindow, stage_day
from app.services.boards.org_config import due_reminder_time
from app.services.leave.digest_settings import org_zone
from app.services.notifications import NotificationCategory
from app.services.scheduling.pace import Pace
from app.services.scheduling.tick_loop import due_local_date, run_tick_loop
from app.services.slack_dm import send_each

logger = structlog.get_logger(__name__)


def fire_window(org: DueOrg, now: datetime) -> FireWindow | None:
    """The org's local day if its reminders are due at ``now``, else None (no I/O)."""
    zone = org_zone(org.config, org.policy_timezone, org.org_id)
    window = timedelta(minutes=settings.boards.due_reminder_window_minutes)
    day = due_local_date(now, zone, due_reminder_time(org.config, org.org_id), window=window)
    if day is None:
        return None
    return FireWindow(
        day=day,
        zone=zone,
        day_start=datetime.combine(day, time(), tzinfo=zone),
        day_end=datetime.combine(day + timedelta(days=1), time(), tzinfo=zone),
    )


async def tick_once(now_utc: datetime | None = None) -> None:
    """One pass over every org with open cards due soon."""
    now = now_utc or datetime.now(UTC)
    cfg = settings.boards
    async with AsyncSessionLocal() as db:
        orgs = await orgs_with_due_cards(
            db, now + timedelta(hours=cfg.due_reminder_lookahead_hours)
        )
    slots = asyncio.Semaphore(cfg.due_reminder_org_concurrency)

    async def _one(org: DueOrg) -> None:
        async with slots:
            try:
                await org_pass(org, now)
            except Exception:
                logger.exception("board_due_org_failed", org_id=str(org.org_id))

    await asyncio.gather(*(_one(org) for org in orgs))


async def org_pass(org: DueOrg, now: datetime) -> None:
    """Send the org's reminders if they're due now; nothing at all outside its window."""
    window = fire_window(org, now)
    if window is None:
        return
    org_id, cfg = org.org_id, settings.boards
    async with AsyncSessionLocal() as db:
        texts = await stage_day(db, org_id, window)
        await db.commit()
    if not texts:
        return
    pace = Pace(cfg.due_reminder_dm_concurrency, cfg.due_reminder_dm_interval_seconds)
    reached = await send_each(org_id, NotificationCategory.BOARD_DUE_REMINDERS, texts, pace=pace)
    async with AsyncSessionLocal() as db:
        claims = DigestClaimRepository(db, org_id=org_id)
        for user_id in texts:
            status = _outcome(reached.get(user_id))
            error = "slack_failed" if status is DigestClaimStatus.FAILED else None
            await claims.finish(KIND, user_id, window.day, status, error)
        await db.commit()
    logger.info("board_due_sent", org_id=str(org_id), people=len(texts), reached=len(reached))


def _outcome(reached: bool | None) -> DigestClaimStatus:
    """Sent, failed (retried by a later tick), or skipped (no Slack, not linked, or muted)."""
    if reached is None:
        return DigestClaimStatus.SKIPPED
    return DigestClaimStatus.SENT if reached else DigestClaimStatus.FAILED


async def run_forever() -> None:
    """Tick every ``BoardsConfig.due_reminder_tick_seconds`` until cancelled."""
    await run_tick_loop("board_due", settings.boards.due_reminder_tick_seconds, tick_once)
