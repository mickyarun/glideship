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

"""Tell people about their cards: assigned to one, or a comment on one they're on.

Nobody hears about their own action. Recipients are narrowed to people who
can still open the board, so someone removed from it stops hearing about
its cards; Slack DMs then go through the ``board_cards`` category, which
members can mute. Imports never call these: their writes don't go through
the card services that stage notices.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.board import Board
from app.models.board_card import BoardCard
from app.models.notification import NotificationType
from app.repositories.board_access import BoardAccessRepository
from app.repositories.board_card_links import BoardCardLinkRepository
from app.repositories.user import UserRepository
from app.services.boards.access import BoardAccess
from app.services.boards.reads import card_key
from app.services.notifications import NotificationCategory
from app.services.notifications.notice import Notice, escape_mrkdwn, stage_notice

SOMEONE = "Someone"


def card_path(board_key: str, number: int) -> str:
    """The card's page in the app, e.g. ``/boards/OPS/cards/12``."""
    return f"/boards/{board_key}/cards/{number}"


def _slack_text(board: Board, card: BoardCard, lead: str) -> str:
    url = f"{settings.frontend_url}{card_path(board.key, card.number)}"
    key = card_key(board, card.number)
    return (
        f"{escape_mrkdwn(lead)} *{key}* {escape_mrkdwn(card.title)}"
        f" on {escape_mrkdwn(board.name)}. <{url}|Open card>"
    )


async def _actor_name(db: AsyncSession, access: BoardAccess) -> str:
    people = await UserRepository(db, org_id=access.org_id).get_people_by_ids({access.user_id})
    person = people.get(access.user_id)
    return person.name if person else SOMEONE


async def _stage(
    db: AsyncSession,
    access: BoardAccess,
    card: BoardCard,
    user_ids: set[uuid.UUID],
    *,
    kind: NotificationType,
    title: str,
    verb: str,
) -> Notice | None:
    wanted = user_ids - {access.user_id}
    repo = BoardAccessRepository(db, org_id=access.org_id)
    recipients = await repo.users_with_access(access.board.id, wanted)
    if not recipients:
        return None
    board = access.board
    lead = f"{await _actor_name(db, access)} {verb}"
    key = card_key(board, card.number)
    return stage_notice(
        db,
        org_id=access.org_id,
        user_ids=recipients,
        kind=kind,
        category=NotificationCategory.BOARD_CARDS,
        title=title,
        message=f"{lead} {key} {card.title} on {board.name}.",
        link=card_path(board.key, card.number),
        slack_text=_slack_text(board, card, lead),
    )


async def stage_assigned(
    db: AsyncSession, access: BoardAccess, card: BoardCard, user_ids: set[uuid.UUID]
) -> Notice | None:
    """People newly assigned to ``card`` by someone else; None when nobody is told."""
    return await _stage(
        db,
        access,
        card,
        user_ids,
        kind=NotificationType.BOARD_CARD_ASSIGNED,
        title="Assigned to a card",
        verb="assigned you to",
    )


async def stage_commented(db: AsyncSession, access: BoardAccess, card: BoardCard) -> Notice | None:
    """The card's assignees hear about a comment that isn't their own."""
    assignees = await BoardCardLinkRepository(db, org_id=access.org_id).assignee_ids(card.id)
    return await _stage(
        db,
        access,
        card,
        assignees,
        kind=NotificationType.BOARD_CARD_COMMENT,
        title="New comment on your card",
        verb="commented on",
    )


def send(notice: Notice | None) -> None:
    """Send a staged notice, if there is one. Call after commit."""
    if notice is not None:
        notice.send()
