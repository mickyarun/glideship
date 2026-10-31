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
in the leave digest's timezone. Each person gets one in-app notification and
one Slack DM a day: a ``digest_claims`` row claimed in the same transaction
as the in-app row makes that at most once, across ticks, restarts and
instances. People who lost access to a board don't hear about its cards.
"""

import uuid
from collections import defaultdict
from datetime import UTC, datetime, time, timedelta, tzinfo
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.digest_claim import DigestClaimKind, DigestClaimStatus
from app.models.notification import NotificationType
from app.repositories.board_access import BoardAccessRepository
from app.repositories.board_due import BoardDueRepository, DueCard, orgs_with_due_cards
from app.repositories.digest_claim import DigestClaimRepository
from app.services.after_commit import publish_after_commit
from app.services.boards.due_compose import BOARDS_PATH, compose_due
from app.services.boards.org_config import due_reminder_time
from app.services.leave.digest_settings import org_zone
from app.services.notifications import NotificationCategory
from app.services.notifications.notice import add_notification_rows
from app.services.scheduling.tick_loop import due_local_date, run_tick_loop
from app.services.slack_dm import send_each

logger = structlog.get_logger(__name__)
KIND = DigestClaimKind.BOARD_DUE
# Further ahead than any timezone's end of today, so no org with cards due
# today is skipped before its own local day is worked out.
LOOKAHEAD = timedelta(days=2)


async def tick_once(now_utc: datetime | None = None) -> None:
    """One pass over every org with open cards due soon."""
    now = now_utc or datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        orgs = await orgs_with_due_cards(db, now + LOOKAHEAD)
    for org_id, config in orgs:
        try:
            await org_pass(org_id, config, now)
        except Exception:
            logger.exception("board_due_org_failed", org_id=str(org_id))


async def org_pass(org_id: uuid.UUID, config: dict[str, Any] | None, now: datetime) -> None:
    """Send the org's reminders if they're due now and not yet sent today."""
    async with AsyncSessionLocal() as db:
        zone = await org_zone(db, org_id, config)
        day = due_local_date(now, zone, due_reminder_time(config, org_id))
        if day is None:
            return
        day_start = datetime.combine(day, time(), tzinfo=zone)
        day_end = datetime.combine(day + timedelta(days=1), time(), tzinfo=zone)
        cards = await BoardDueRepository(db, org_id=org_id).due_by_assignee(day_end)
        texts = await _claim_and_stage(
            db, org_id, day_start, zone, await _reachable(db, org_id, cards)
        )
        await db.commit()
    if not texts:
        return
    reached = await send_each(org_id, NotificationCategory.BOARD_DUE_REMINDERS, texts)
    async with AsyncSessionLocal() as db:
        claims = DigestClaimRepository(db, org_id=org_id)
        for user_id in texts:
            status = _outcome(reached.get(user_id))
            error = "slack_failed" if status is DigestClaimStatus.FAILED else None
            await claims.finish(KIND, user_id, day, status, error)
        await db.commit()
    logger.info("board_due_sent", org_id=str(org_id), people=len(texts), reached=len(reached))


def _outcome(reached: bool | None) -> DigestClaimStatus:
    """Sent, failed, or skipped (no Slack, not linked, or muted: in-app only)."""
    if reached is None:
        return DigestClaimStatus.SKIPPED
    return DigestClaimStatus.SENT if reached else DigestClaimStatus.FAILED


async def _reachable(
    db: AsyncSession, org_id: uuid.UUID, cards: list[DueCard]
) -> dict[uuid.UUID, list[DueCard]]:
    """Each person's cards, keeping only boards they can still open."""
    by_board: dict[uuid.UUID, list[DueCard]] = defaultdict(list)
    for card in cards:
        by_board[card.board_id].append(card)
    access = BoardAccessRepository(db, org_id=org_id)
    allowed: set[tuple[uuid.UUID, uuid.UUID]] = set()
    for board_id, rows in by_board.items():
        people = await access.users_with_access(board_id, {row.user_id for row in rows})
        allowed |= {(board_id, person) for person in people}
    mine: dict[uuid.UUID, list[DueCard]] = defaultdict(list)
    for card in cards:
        if (card.board_id, card.user_id) in allowed:
            mine[card.user_id].append(card)
    return mine


async def _claim_and_stage(
    db: AsyncSession,
    org_id: uuid.UUID,
    day_start: datetime,
    zone: tzinfo,
    mine: dict[uuid.UUID, list[DueCard]],
) -> dict[uuid.UUID, str]:
    """Claim each person's day and add their in-app row; the Slack text per claim won."""
    claims = DigestClaimRepository(db, org_id=org_id)
    texts: dict[uuid.UUID, str] = {}
    for user_id in sorted(mine):
        if not await claims.claim(KIND, user_id, day_start.date()):
            continue
        message = compose_due(
            mine[user_id],
            day_start=day_start,
            zone=zone,
            max_cards=settings.boards.due_reminder_max_cards,
            base_url=settings.frontend_url,
        )
        events = add_notification_rows(
            db,
            org_id=org_id,
            user_ids={user_id},
            kind=NotificationType.BOARD_DUE,
            title=message.title,
            message=message.message,
            link=BOARDS_PATH,
        )
        for topic, payload in events:
            publish_after_commit(db, topic, payload)
        texts[user_id] = message.slack_text
    return texts


async def run_forever() -> None:
    """Tick every ``BoardsConfig.due_reminder_tick_seconds`` until cancelled."""
    await run_tick_loop("board_due", settings.boards.due_reminder_tick_seconds, tick_once)
