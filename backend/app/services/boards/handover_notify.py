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

"""Tell a handed-over BUD's owner: "SEO-14 was handed over as BUD-123".

The owner is whoever the BUD is assigned to once its stage has started, so
this runs after assignment. Nobody hears about their own handover. The DM
goes through ``board_handovers``, which people can mute; the in-app row is
``board_handover`` and opens the BUD. The card's key is named as the BUD's
requirements name it (their "From the board" link), whoever the owner is.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.board_card import BoardCard
from app.models.bud import BUDDocument
from app.models.notification import NotificationType
from app.services.boards.access import BoardAccess
from app.services.boards.handover_similar import bud_key
from app.services.boards.reads import card_key
from app.services.notifications import NotificationCategory
from app.services.notifications.notice import Notice, stage_notice
from app.services.slack_mrkdwn import escape_mrkdwn

TITLE = "A card was handed over to you"


def bud_number_path(number: int) -> str:
    """A BUD's page in the app by its number, e.g. ``/buds/123``."""
    return f"/buds/{number}"


def bud_path(bud: BUDDocument) -> str:
    """The BUD's page in the app, e.g. ``/buds/123``."""
    return bud_number_path(bud.bud_number)


async def stage_owner_notice(
    db: AsyncSession, access: BoardAccess, card: BoardCard, bud: BUDDocument
) -> Notice | None:
    """Stage the owner's in-app row and DM; None when there's nobody to tell."""
    owner = bud.assignee_id
    if owner is None or owner == access.user_id:
        return None
    source = card_key(access.board.key, card.number)
    key = bud_key(bud.bud_number)
    link = bud_path(bud)
    lead = f"{source} was handed over as"
    return stage_notice(
        db,
        org_id=access.org_id,
        user_ids={owner},
        kind=NotificationType.BOARD_HANDOVER,
        category=NotificationCategory.BOARD_HANDOVERS,
        title=TITLE,
        message=f"{lead} {key} {bud.title}.",
        link=link,
        slack_text=(
            f"{escape_mrkdwn(lead)} *{key}* {escape_mrkdwn(bud.title)}."
            f" <{settings.frontend_url}{link}|Open BUD>"
        ),
    )
