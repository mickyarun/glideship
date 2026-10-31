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

"""Each card's active agent run as a chip, inside the card summary query.

One correlated ``jsonb_build_object`` per card, like the handover chips, so
a page of cards still loads in one round trip. A card has at most one
pending or running run (the partial unique index), so there is at most one
chip; its skill's name is null when the skill was deleted.
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select

from app.models.agent_skill import AgentSkill
from app.models.board_agent import ACTIVE_RUN_STATUSES, BoardAgentRunStatus, BoardCardAgentRun
from app.models.board_card import BoardCard


@dataclass(frozen=True)
class RunChipRow:
    """The card's pending or running run: its status and its skill's name."""

    status: BoardAgentRunStatus
    skill_name: str | None


def active_run_chip() -> Any:
    """The card's active run as JSON, or null when none is going."""
    chip = func.jsonb_build_object(
        "status", BoardCardAgentRun.status, "skill_name", AgentSkill.name
    )
    return (
        select(chip)
        .select_from(BoardCardAgentRun)
        .outerjoin(AgentSkill, AgentSkill.id == BoardCardAgentRun.skill_id)
        .where(
            BoardCardAgentRun.card_id == BoardCard.id,
            BoardCardAgentRun.org_id == BoardCard.org_id,
            BoardCardAgentRun.status.in_(ACTIVE_RUN_STATUSES),
        )
        .correlate(BoardCard)
        .limit(1)
        .scalar_subquery()
    )


def parse_run_chip(raw: dict[str, Any] | None) -> RunChipRow | None:
    """The aggregated JSON as a typed row."""
    if raw is None:
        return None
    return RunChipRow(status=BoardAgentRunStatus(raw["status"]), skill_name=raw["skill_name"])
