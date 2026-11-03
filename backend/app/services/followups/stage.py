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

"""One org's follow-ups for the people due now, staged in the caller's transaction.

Everyone due now is claimed for their local day, whether or not they end
up with a message, so later ticks in the same window skip them without
reading anything. People away that day or with nothing due are finished
as skipped on the spot. Failed sends, and claims left unfinished longer
than ``FollowupsConfig.stale_minutes``, are re-claimed (up to
``max_retries`` times) and composed again from what is due now.
"""

import uuid
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.digest_claim import DigestClaimKind, DigestClaimStatus
from app.repositories.digest_claim import DigestClaimRepository
from app.repositories.followup_away import AwayRepository
from app.services.followups.compose import FollowupMessage, compose_followups
from app.services.followups.due_state import LocalDay
from app.services.followups.gather import gather_items

KIND = DigestClaimKind.DAILY_FOLLOWUPS
AWAY = "away"
NOTHING_DUE = "nothing_due"


async def stage_org(
    db: AsyncSession, org_id: uuid.UUID, due: dict[uuid.UUID, LocalDay]
) -> dict[uuid.UUID, FollowupMessage]:
    """Claim the people in ``due`` for their day; the message to DM each one now."""
    claims = DigestClaimRepository(db, org_id=org_id)
    taken = await _claim(claims, due)
    away: set[uuid.UUID] = set()
    for day, people in _by_day({u: due[u] for u in taken}).items():
        away |= await AwayRepository(db, org_id=org_id).away_on(people, day)
    for user_id in sorted(away):
        await claims.finish(KIND, user_id, due[user_id].day, DigestClaimStatus.SKIPPED, AWAY)
    working = {u: due[u] for u in taken - away}
    items = await gather_items(db, org_id, working)
    for user_id in sorted(set(working) - set(items)):
        day = due[user_id].day
        await claims.finish(KIND, user_id, day, DigestClaimStatus.SKIPPED, NOTHING_DUE)
    cfg = settings.followups
    return {
        user_id: compose_followups(
            mine,
            working[user_id],
            max_items=cfg.max_items,
            comment_chars=cfg.comment_chars,
            base_url=settings.frontend_url,
        )
        for user_id, mine in items.items()
    }


async def _claim(claims: DigestClaimRepository, due: dict[uuid.UUID, LocalDay]) -> set[uuid.UUID]:
    """Re-claim retryable claims, then claim everyone else who has none for their day."""
    cfg = settings.followups
    taken: set[uuid.UUID] = set()
    for day, people in _by_day(due).items():
        taken |= set(
            await claims.reclaim_retryable(
                KIND,
                day,
                max_retries=cfg.max_retries,
                stale=timedelta(minutes=cfg.stale_minutes),
                user_ids=people,
            )
        )
    for user_id in sorted(set(due) - taken):
        if await claims.claim(KIND, user_id, due[user_id].day):
            taken.add(user_id)
    return taken


def _by_day(due: dict[uuid.UUID, LocalDay]) -> dict[date, set[uuid.UUID]]:
    grouped: dict[date, set[uuid.UUID]] = defaultdict(set)
    for user_id, local in due.items():
        grouped[local.day].add(user_id)
    return grouped
