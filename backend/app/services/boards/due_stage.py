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


"""One org's due reminders for one local day, staged in the caller's transaction.

People with no claim for the day are claimed and get their in-app row in
the same transaction, so that row is written at most once. People whose
Slack message failed, or whose claim was left unfinished longer than
``BoardsConfig.due_reminder_stale_minutes``, are re-claimed (up to
``due_reminder_max_retries`` times) and get the DM again, composed from
their cards as they are now, but no second in-app row. Only boards the
person can still open count. People whose daily follow-ups go out that day
get their cards there instead, so they keep the in-app row but no DM here.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, tzinfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.digest_claim import DigestClaimKind, DigestClaimStatus
from app.models.notification import NotificationType
from app.repositories.board_access import BoardAccessRepository
from app.repositories.board_due import BoardDueRepository, DueCard
from app.repositories.digest_claim import DigestClaimRepository
from app.services.after_commit import publish_after_commit
from app.services.boards.due_compose import BOARDS_PATH, DueMessage, compose_due
from app.services.followups.coverage import covered_by_followups
from app.services.notifications.notice import add_notification_rows

KIND = DigestClaimKind.BOARD_DUE
NOTHING_DUE = "nothing_due"
IN_FOLLOWUPS = "in_followups"


@dataclass(frozen=True)
class FireWindow:
    """The local day whose reminders are due now, and its bounds in its zone."""

    day: date
    zone: tzinfo
    day_start: datetime
    day_end: datetime


async def stage_day(
    db: AsyncSession, org_id: uuid.UUID, window: FireWindow
) -> dict[uuid.UUID, str]:
    """Claim and stage the day's reminders; the Slack text for each person to DM now."""
    cfg = settings.boards
    claims = DigestClaimRepository(db, org_id=org_id)
    retry = set(
        await claims.reclaim_retryable(
            KIND,
            window.day,
            max_retries=cfg.due_reminder_max_retries,
            stale=timedelta(minutes=cfg.due_reminder_stale_minutes),
        )
    )
    due = BoardDueRepository(db, org_id=org_id)
    cards = await due.due_by_assignee(window.day_end, unclaimed=(KIND, window.day))
    if retry:
        cards += await due.due_by_assignee(window.day_end, user_ids=retry)
    mine = await _reachable(db, org_id, cards)
    texts: dict[uuid.UUID, str] = {}
    for user_id in sorted(mine):
        message = _compose(mine[user_id], window)
        if user_id not in retry:
            if not await claims.claim(KIND, user_id, window.day):
                continue
            _add_in_app(db, org_id, user_id, message)
        texts[user_id] = message.slack_text
    for user_id in sorted(retry - set(mine)):
        await claims.finish(KIND, user_id, window.day, DigestClaimStatus.SKIPPED, NOTHING_DUE)
    for user_id in sorted(await covered_by_followups(db, org_id, set(texts), window.day)):
        await claims.finish(KIND, user_id, window.day, DigestClaimStatus.SKIPPED, IN_FOLLOWUPS)
        del texts[user_id]
    return texts


async def _reachable(
    db: AsyncSession, org_id: uuid.UUID, cards: list[DueCard]
) -> dict[uuid.UUID, list[DueCard]]:
    """Each person's cards, keeping only boards they can still open (one query)."""
    allowed = await BoardAccessRepository(db, org_id=org_id).access_pairs(
        {card.board_id for card in cards}, {card.user_id for card in cards}
    )
    mine: dict[uuid.UUID, list[DueCard]] = defaultdict(list)
    for card in cards:
        if (card.board_id, card.user_id) in allowed:
            mine[card.user_id].append(card)
    return mine


def _compose(cards: list[DueCard], window: FireWindow) -> DueMessage:
    return compose_due(
        cards,
        day_start=window.day_start,
        zone=window.zone,
        max_cards=settings.boards.due_reminder_max_cards,
        base_url=settings.frontend_url,
    )


def _add_in_app(
    db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID, message: DueMessage
) -> None:
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
