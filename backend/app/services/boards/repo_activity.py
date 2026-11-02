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


"""Record pull requests and commits that name a card's key as ``repo_activity`` events.

Called from the GitHub webhook with its session, before it commits. The
writes run in a SAVEPOINT, so a failure here is logged and never stops the
delivery's PR bookkeeping. Each touched card's board hears
``card_activity {card_id}`` after the commit, on its own topic only, so a
members-only board's cards never reach anyone else. No XP or SP.
"""

import uuid
from collections import defaultdict
from collections.abc import Mapping
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tracked_repository import TrackedRepository
from app.repositories.board_repo_activity import BoardRepoActivityRepository
from app.services.boards.live import BoardChanges, BoardSocketEvent
from app.services.boards.repo_activity_parse import activities
from app.services.boards.repo_activity_types import RepoActivity

logger = structlog.get_logger(__name__)


async def record_repo_activity(
    db: AsyncSession, repo: TrackedRepository, event_type: str, payload: Mapping[str, Any]
) -> int:
    """Record the delivery's activity on the cards it names; how many events were new.

    Never raises: a malformed payload or a failed write is logged, and the
    delivery's other work (and what it queued for after the commit) goes on.
    """
    try:
        found = activities(event_type, payload, repo.github_repo_full_name)
        if not found:
            return 0
        async with db.begin_nested():
            touched, recorded = await _record(db, repo, found)
    except Exception:
        logger.exception(
            "board_repo_activity_failed", org_id=str(repo.org_id), repo_id=str(repo.id)
        )
        return 0
    for board_id, card_ids in touched.items():
        changes = BoardChanges(board_id, actor_id=None)
        for card_id in sorted(card_ids):
            changes.emit(BoardSocketEvent.CARD_ACTIVITY, card_id=str(card_id))
        changes.queue(db)
    logger.info(
        "board_repo_activity_recorded",
        org_id=str(repo.org_id),
        repo_id=str(repo.id),
        event_type=event_type,
        events=recorded,
    )
    return recorded


async def _record(
    db: AsyncSession, repo: TrackedRepository, found: list[RepoActivity]
) -> tuple[dict[uuid.UUID, set[uuid.UUID]], int]:
    """The cards that got a new event, by board, and how many events were new."""
    events = BoardRepoActivityRepository(db, org_id=repo.org_id)
    touched: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    recorded = 0
    for activity in found:
        for card in await events.cards_named(repo.id, set(activity.keys)):
            fresh = await events.add_once(
                card,
                external_ref=activity.external_ref(repo.id),
                actor_label=activity.author_login,
                detail=activity.detail(repo.id),
            )
            if fresh:
                touched[card.board_id].add(card.id)
                recorded += 1
    return touched, recorded
