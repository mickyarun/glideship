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

"""One line of a follow-ups DM, built from a card or a BUD (pure, no I/O)."""

from dataclasses import dataclass
from datetime import datetime

from app.models.bud import BUDStatus
from app.repositories.board_due import DueCard
from app.repositories.followup_items import LastComment, TargetBud
from app.services.boards.card_notify import card_path
from app.services.boards.handover_notify import bud_number_path
from app.services.boards.handover_similar import bud_key
from app.services.boards.reads import card_key

BUD_STAGE_LABELS: dict[BUDStatus, str] = {
    BUDStatus.BUD: "BUD",
    BUDStatus.DESIGN: "Design",
    BUDStatus.TECH_ARCH: "Tech arch",
    BUDStatus.DEVELOPMENT: "Development",
    BUDStatus.CODE_REVIEW: "Code review",
    BUDStatus.TESTING: "Testing",
    BUDStatus.UAT: "UAT",
    BUDStatus.PROD: "Prod",
    BUDStatus.CLOSED: "Closed",
    BUDStatus.DISCARDED: "Discarded",
}


@dataclass(frozen=True)
class FollowupItem:
    """A card or BUD as one block of the message.

    ``is_target`` marks a BUD's phase target, a forecast rather than a
    promised date, which the message words as "Target" instead of "Due".
    ``can_mark_done`` is for cards, whose due date can be ticked done from
    the message; a BUD's target can't.
    """

    key: str
    title: str
    path: str
    stage: str
    due_at: datetime
    is_target: bool
    can_mark_done: bool
    comment: LastComment | None


def card_item(card: DueCard, comment: LastComment | None) -> FollowupItem:
    """A card, with its board and stage as the stage line."""
    return FollowupItem(
        key=card_key(card.board_key, card.number),
        title=card.title,
        path=card_path(card.board_key, card.number),
        stage=f"{card.board_name} › {card.stage_name}",
        due_at=card.due_at,
        is_target=False,
        can_mark_done=True,
        comment=comment,
    )


def bud_item(bud: TargetBud) -> FollowupItem:
    """A BUD; they have no comment thread, so no last comment."""
    return FollowupItem(
        key=bud_key(bud.bud_number),
        title=bud.title,
        path=bud_number_path(bud.bud_number),
        stage=BUD_STAGE_LABELS.get(bud.status, bud.status.value),
        due_at=bud.target_at,
        is_target=True,
        can_mark_done=False,
        comment=None,
    )
