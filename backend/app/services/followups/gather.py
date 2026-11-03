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

"""Each person's follow-up items for their own local day, read in a few queries.

Cards they're assigned (on boards they can still open) and BUDs they own,
due before the end of their day plus ``FollowupsConfig.soon_days``. One
read per kind covers everyone, using the latest cutoff; each person's list
is then trimmed to their own.
"""

import uuid
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.repositories.board_access import BoardAccessRepository
from app.repositories.board_due import BoardDueRepository
from app.repositories.followup_items import FollowupItemsRepository
from app.services.followups.due_state import LocalDay
from app.services.followups.items import FollowupItem, bud_item, card_item


def cutoff(local: LocalDay) -> datetime:
    """Items due before this are in the person's message."""
    return local.end + timedelta(days=settings.followups.soon_days)


async def gather_items(
    db: AsyncSession, org_id: uuid.UUID, days: dict[uuid.UUID, LocalDay]
) -> dict[uuid.UUID, list[FollowupItem]]:
    """The items for each of ``days``' people who has any."""
    if not days:
        return {}
    latest = max(cutoff(local) for local in days.values())
    people = set(days)
    cards = await BoardDueRepository(db, org_id=org_id).due_by_assignee(latest, user_ids=people)
    allowed = await BoardAccessRepository(db, org_id=org_id).access_pairs(
        {c.board_id for c in cards}, {c.user_id for c in cards}
    )
    cards = [c for c in cards if (c.board_id, c.user_id) in allowed]
    repo = FollowupItemsRepository(db, org_id=org_id)
    comments = await repo.last_card_comments({c.card_id for c in cards})
    found: dict[uuid.UUID, list[FollowupItem]] = defaultdict(list)
    for card in cards:
        found[card.user_id].append(card_item(card, comments.get(card.card_id)))
    for bud in await repo.bud_targets(people, latest):
        found[bud.user_id].append(bud_item(bud))
    mine = {
        user_id: [i for i in items if i.due_at < cutoff(days[user_id])]
        for user_id, items in found.items()
    }
    return {user_id: items for user_id, items in mine.items() if items}
