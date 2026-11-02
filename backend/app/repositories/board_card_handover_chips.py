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

"""Each card's handovers as chips, aggregated inside the card summary query.

One correlated jsonb_agg per card, like the summary's other columns, so
a page of cards still loads in one round trip. A handover whose BUD was
deleted has no chip.
"""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, literal_column, select
from sqlalchemy.dialects.postgresql import aggregate_order_by

from app.models.board_card import BoardCard
from app.models.board_enums import BoardHandoverStatus
from app.models.board_handover import BoardCardHandover
from app.models.bud import BUDDocument, BUDStatus


@dataclass(frozen=True)
class HandoverChipRow:
    """One handover on a card: its BUD's id, number and status, and the handover's."""

    bud_id: uuid.UUID
    bud_number: int
    status: BUDStatus
    handover_status: BoardHandoverStatus


def handover_chips() -> Any:
    """The card's chips as a JSON array, oldest handover first (empty when none)."""
    chip = func.jsonb_build_object(
        "bud_id",
        BoardCardHandover.bud_id,
        "bud_number",
        BUDDocument.bud_number,
        "status",
        BUDDocument.status,
        "handover_status",
        BoardCardHandover.status,
    )
    ordered = aggregate_order_by(chip, BoardCardHandover.handed_over_at, BoardCardHandover.id)
    return (
        select(func.coalesce(func.jsonb_agg(ordered), literal_column("'[]'::jsonb")))
        .select_from(BoardCardHandover)
        .join(
            BUDDocument,
            (BUDDocument.id == BoardCardHandover.bud_id)
            & (BUDDocument.org_id == BoardCardHandover.org_id),
        )
        .where(
            BoardCardHandover.card_id == BoardCard.id,
            BoardCardHandover.org_id == BoardCard.org_id,
        )
        .correlate(BoardCard)
        .scalar_subquery()
    )


def parse_chips(raw: list[dict[str, Any]] | None) -> list[HandoverChipRow]:
    """The aggregated JSON as typed rows."""
    return [
        HandoverChipRow(
            bud_id=uuid.UUID(item["bud_id"]),
            bud_number=int(item["bud_number"]),
            status=BUDStatus(item["status"]),
            handover_status=BoardHandoverStatus(item["handover_status"]),
        )
        for item in raw or []
    ]
