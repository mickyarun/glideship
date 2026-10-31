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

"""A card's BUD chips and its delivery roll-up, and who may open the BUDs they name.

Everyone who can see the card sees each chip's BUD key and statuses, so a
board tracks delivery without engineering access. Only callers holding
``buds:view`` and ``workspace:engineering`` get ``can_open_bud``; nobody gets
a BUD's title from a board.
"""

from collections.abc import Sequence

from app.core.permissions import WORKSPACE_ENGINEERING
from app.models.board_enums import BoardHandoverStatus
from app.models.bud import BUDStatus
from app.repositories.board_access import PermissionChecker
from app.repositories.board_card_handover_chips import HandoverChipRow
from app.schemas.boards.card import CardDelivery, HandoverChip
from app.services.boards.handover_similar import bud_key

BUDS_VIEW = "buds:view"
# A BUD counts as delivered once it reaches prod; closing it comes later.
DELIVERED_STATUSES = frozenset({BUDStatus.PROD, BUDStatus.CLOSED})


def opens_buds(perms: PermissionChecker) -> bool:
    """Whether the caller may open a BUD a chip names."""
    return perms.has(BUDS_VIEW) and perms.has(WORKSPACE_ENGINEERING)


def chips(rows: Sequence[HandoverChipRow], *, can_open_bud: bool) -> list[HandoverChip]:
    """The card's chips, oldest handover first."""
    return [
        HandoverChip(
            bud_id=row.bud_id,
            bud_key=bud_key(row.bud_number),
            status=row.status,
            handover_status=row.handover_status,
            can_open_bud=can_open_bud,
        )
        for row in rows
    ]


def all_delivered(statuses: Sequence[BUDStatus]) -> bool:
    """Whether there is at least one live handover and every one has reached prod."""
    return bool(statuses) and all(status in DELIVERED_STATUSES for status in statuses)


def delivery(rows: Sequence[HandoverChipRow]) -> CardDelivery:
    """``none`` without a live handover, ``delivered`` when all reached prod, else in progress."""
    live = [row.status for row in rows if row.handover_status is BoardHandoverStatus.ACTIVE]
    if not live:
        return CardDelivery.NONE
    return CardDelivery.DELIVERED if all_delivered(live) else CardDelivery.IN_PROGRESS
