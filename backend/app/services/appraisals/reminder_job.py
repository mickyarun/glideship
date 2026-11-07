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

"""The reminder tick: appraisal DMs once a day at the org's local send time.

Only orgs with Slack connected get anything; the creation tick runs for
everyone regardless. Each pass first leaves out people already reached
today, then for each kind claims a ``digest_claims`` row per person,
sends, and records the outcome before moving to the next kind, so a
claim is never held while other kinds go out. A failed send, or a claim
left unfinished, is retried on a later tick that day with the message as
it reads then. Delivered or undeliverable (muted, not linked), the
openings a message announced are marked, so they aren't announced again.
"""

import asyncio
import uuid
from datetime import UTC, date, datetime, timedelta

import structlog

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.digest_claim import DigestClaimKind, DigestClaimStatus
from app.repositories.appraisal_check_in import AppraisalCheckInRepository
from app.repositories.appraisal_cycle import CycleOrg, orgs_with_running_cycles
from app.repositories.appraisal_feedback import AppraisalFeedbackRepository
from app.repositories.digest_claim import DigestClaimRepository
from app.services.appraisals.reminder_stage import Outbox, compose_day
from app.services.leave.digest_settings import org_zone
from app.services.notifications import NotificationCategory
from app.services.scheduling.claim_outcome import claim_outcome
from app.services.scheduling.pace import Pace
from app.services.scheduling.tick_loop import due_local_date, run_tick_loop
from app.services.slack_dm import bot_token, send_each

logger = structlog.get_logger(__name__)
CATEGORY = NotificationCategory.APPRAISAL_REMINDERS
KINDS = (
    DigestClaimKind.APPRAISAL_CHECK_IN_READY,
    DigestClaimKind.APPRAISAL_FEEDBACK_DUE,
    DigestClaimKind.APPRAISAL_HR_OVERDUE,
)


def _stale() -> timedelta:
    return timedelta(minutes=settings.appraisals.stale_minutes)


async def _claim(org_id: uuid.UUID, kind: DigestClaimKind, outbox: Outbox, day: date) -> Outbox:
    """Claim this kind's messages: new claims, and retries of failed or stuck ones."""
    async with AsyncSessionLocal() as db:
        claims = DigestClaimRepository(db, org_id=org_id)
        retry = set(
            await claims.reclaim_retryable(
                kind,
                day,
                max_retries=settings.appraisals.max_retries,
                stale=_stale(),
                user_ids=set(outbox),
            )
        )
        mine: Outbox = {}
        for user_id in sorted(outbox):
            if user_id in retry or await claims.claim(kind, user_id, day):
                mine[user_id] = outbox[user_id]
        await db.commit()
    return mine


async def _send(org_id: uuid.UUID, kind: DigestClaimKind, outbox: Outbox, day: date) -> None:
    """Send one kind's claimed messages and record each outcome."""
    cfg = settings.appraisals
    texts = {user_id: message.text for user_id, message in outbox.items()}
    reached = await send_each(
        org_id, CATEGORY, texts, pace=Pace(cfg.dm_concurrency, cfg.dm_interval_seconds)
    )
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        claims = DigestClaimRepository(db, org_id=org_id)
        told_check_ins: list[uuid.UUID] = []
        told_feedback: list[uuid.UUID] = []
        for user_id, message in outbox.items():
            status = claim_outcome(reached.get(user_id))
            error = "slack_failed" if status is DigestClaimStatus.FAILED else None
            await claims.finish(kind, user_id, day, status, error)
            if status is not DigestClaimStatus.FAILED:
                told_check_ins += message.check_ins
                told_feedback += message.feedback
        await AppraisalCheckInRepository(db, org_id=org_id).mark_notified(told_check_ins, now)
        await AppraisalFeedbackRepository(db, org_id=org_id).mark_notified(told_feedback, now)
        await db.commit()
    logger.info(
        "appraisal_reminders_sent",
        org_id=str(org_id),
        kind=kind.value,
        people=len(outbox),
        reached=len(reached),
    )


async def org_pass(org: CycleOrg, now: datetime) -> None:
    """Send the org's reminders if they're due now; nothing outside its window."""
    cfg = settings.appraisals
    zone = org_zone(org.config, org.policy_timezone, org.org_id)
    window = timedelta(minutes=cfg.reminder_window_minutes)
    day = due_local_date(now, zone, cfg.reminder_time, window=window)
    if day is None:
        return
    async with AsyncSessionLocal() as db:
        if not await bot_token(db, org.org_id):
            return
        claims = DigestClaimRepository(db, org_id=org.org_id)
        skip = {
            kind: await claims.settled_users(
                kind, day, max_retries=cfg.max_retries, stale=_stale()
            )
            for kind in KINDS
        }
        composed = await compose_day(db, org.org_id, day, skip)
    for kind, outbox in composed.items():
        mine = await _claim(org.org_id, kind, outbox, day) if outbox else {}
        if mine:
            await _send(org.org_id, kind, mine, day)


async def tick_once(now_utc: datetime | None = None) -> None:
    """One pass over every org with a running cycle; one failing never stops the rest."""
    now = now_utc or datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        orgs = await orgs_with_running_cycles(db)
    slots = asyncio.Semaphore(settings.appraisals.org_concurrency)

    async def _one(org: CycleOrg) -> None:
        async with slots:
            try:
                await org_pass(org, now)
            except Exception:
                logger.exception("appraisal_reminders_org_failed", org_id=str(org.org_id))

    await asyncio.gather(*(_one(org) for org in orgs))


async def run_reminder_scheduler() -> None:
    """The long-running loop started from the app's lifespan."""
    await run_tick_loop(
        "appraisal_reminders", settings.appraisals.reminder_tick_seconds, tick_once
    )
