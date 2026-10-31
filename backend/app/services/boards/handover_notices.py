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

"""Tell a card's assignees how its BUDs are doing: sent back, or delivered.

Recipients are the card's assignees who can still open its board, minus
whoever acted (nobody, for an automatic close). The in-app row opens the
card; the DM goes through ``board_handovers``, which people can mute. The
text names the BUD by key and the card by key and title, never the BUD's
title: a card assignee may not have engineering access.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.board import Board
from app.models.board_card import BoardCard
from app.models.notification import NotificationType
from app.repositories.board_access import BoardAccessRepository
from app.repositories.board_card_links import BoardCardLinkRepository
from app.services.boards.card_notify import card_path
from app.services.boards.reads import card_key
from app.services.notifications import NotificationCategory
from app.services.notifications.notice import Notice, stage_notice
from app.services.slack_mrkdwn import escape_mrkdwn

RETURNED_TITLE = "A BUD was sent back to your card"
DELIVERED_TITLE = "Your card's BUD reached prod"


async def _stage(
    db: AsyncSession,
    board: Board,
    card: BoardCard,
    *,
    actor_id: uuid.UUID | None,
    kind: NotificationType,
    title: str,
    lead: str,
    tail: str = "",
) -> Notice | None:
    assignees = await BoardCardLinkRepository(db, org_id=card.org_id).assignee_ids(card.id)
    wanted = assignees - ({actor_id} if actor_id else set())
    repo = BoardAccessRepository(db, org_id=card.org_id)
    recipients = await repo.users_with_access(board.id, wanted)
    if not recipients:
        return None
    key = card_key(board.key, card.number)
    path = card_path(board.key, card.number)
    url = f"{settings.frontend_url}{path}"
    return stage_notice(
        db,
        org_id=card.org_id,
        user_ids=recipients,
        kind=kind,
        category=NotificationCategory.BOARD_HANDOVERS,
        title=title,
        message=f"{lead} {key} {card.title}{tail}",
        link=path,
        slack_text=(
            f"{escape_mrkdwn(lead)} *{key}* {escape_mrkdwn(card.title)}"
            f"{escape_mrkdwn(tail)} <{url}|Open card>"
        ),
    )


async def stage_returned(
    db: AsyncSession,
    board: Board,
    card: BoardCard,
    *,
    bud_key: str,
    actor_id: uuid.UUID,
    reason: str,
) -> Notice | None:
    """ "<BUD-012> was sent back to <SEO-14 Title>: <reason>"; None when nobody hears."""
    return await _stage(
        db,
        board,
        card,
        actor_id=actor_id,
        kind=NotificationType.BOARD_HANDOVER_RETURNED,
        title=RETURNED_TITLE,
        lead=f"{bud_key} was sent back to",
        tail=f": {reason}",
    )


async def stage_delivered(
    db: AsyncSession,
    board: Board,
    card: BoardCard,
    *,
    bud_key: str,
    actor_id: uuid.UUID | None,
) -> Notice | None:
    """ "<BUD-012> from <SEO-14 Title> reached prod."; None when nobody hears."""
    return await _stage(
        db,
        board,
        card,
        actor_id=actor_id,
        kind=NotificationType.BOARD_HANDOVER_DELIVERED,
        title=DELIVERED_TITLE,
        lead=f"{bud_key} from",
        tail=" reached prod.",
    )
