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

"""Cards: a column's summaries, one card's detail, and edits and moves."""

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.models.board_agent import BoardAgentRunStatus
from app.models.board_enums import BoardHandoverStatus
from app.models.bud import BUDPriority, BUDStatus
from app.schemas.boards.text import CardDescription, CardTitle, IdList
from app.services.boards.constants import BOARD_KEY_MAX_LENGTH


class CardCreate(BaseModel):
    """A new card, at the bottom of ``stage_id`` or of the default stage."""

    model_config = ConfigDict(extra="forbid")

    title: CardTitle
    description_md: CardDescription = None
    stage_id: uuid.UUID | None = None
    priority: BUDPriority | None = None
    start_at: AwareDatetime | None = None
    due_at: AwareDatetime | None = None
    assignee_ids: IdList = Field(default_factory=list)
    label_ids: IdList = Field(default_factory=list)
    # One of the board's linked repositories.
    repo_id: uuid.UUID | None = None
    # Same rule as a move into a ``done`` stage.
    confirm_open_checklist: bool = False


class CardUpdate(BaseModel):
    """Card edits. Omitted fields stay; ``null`` clears a nullable field."""

    model_config = ConfigDict(extra="forbid")

    title: CardTitle | None = None
    description_md: CardDescription = None
    priority: BUDPriority | None = None
    start_at: AwareDatetime | None = None
    due_at: AwareDatetime | None = None
    due_done: bool | None = None
    assignee_ids: IdList | None = None
    label_ids: IdList | None = None
    repo_id: uuid.UUID | None = None


class CardMove(BaseModel):
    """Where a card goes on its board: after one card and/or before another.

    With neither neighbour the card goes to the bottom of the stage. Moving
    into a ``done`` stage with open checklist items needs
    ``confirm_open_checklist``.
    """

    model_config = ConfigDict(extra="forbid")

    stage_id: uuid.UUID
    after_id: uuid.UUID | None = None
    before_id: uuid.UUID | None = None
    confirm_open_checklist: bool = False


class CardMoveBoard(BaseModel):
    """Move a card to another board, to the bottom of a stage there.

    Without ``stage_id`` the card goes to the stage with the same name, else
    the first stage of the same category, else the target's default stage.
    The target stage's entry rules apply, ``confirm_open_checklist`` as for
    a move.
    """

    model_config = ConfigDict(extra="forbid")

    target_board_key: str = Field(min_length=1, max_length=BOARD_KEY_MAX_LENGTH)
    stage_id: uuid.UUID | None = None
    confirm_open_checklist: bool = False


class HandoverHistoryKind(StrEnum):
    """What happened to a handover after it was first made."""

    RETURNED = "returned"
    HANDED_OVER_AGAIN = "handed_over_again"


class HandoverHistoryEntry(BaseModel):
    """One send-back or re-handover of a card's BUD, from the card's own events.

    ``reason`` is a send-back's (already posted on the card as a comment);
    ``by_name`` is whoever did it, when known.
    """

    at: datetime
    kind: HandoverHistoryKind
    reason: str | None = None
    by_name: str | None = None


class HandoverChip(BaseModel):
    """A BUD this card was handed over to: its key and statuses, never its title.

    ``can_open_bud`` is whether the caller may open the BUD (``buds:view``
    and ``workspace:engineering``); socket payloads always send false, and
    a client merging one keeps the value it last fetched. ``history`` (newest
    first) is filled on the card's own detail and empty on board pages and sockets.
    """

    bud_id: uuid.UUID
    bud_key: str
    status: BUDStatus
    handover_status: BoardHandoverStatus
    can_open_bud: bool = False
    history: list[HandoverHistoryEntry] = Field(default_factory=list)


class CardDelivery(StrEnum):
    """How far the card's live handovers are: none, some still in dev, all in prod."""

    NONE = "none"
    IN_PROGRESS = "in_progress"
    DELIVERED = "delivered"


class CardAgentRun(BaseModel):
    """The agent run going on a card now (pending or running), for its tile.

    ``skill_name`` is null when the run's skill was deleted.
    """

    status: BoardAgentRunStatus
    skill_name: str | None


class CardSummary(BaseModel):
    """A card as a board column shows it; ``agent_run`` is its active run, if any."""

    id: uuid.UUID
    key: str
    number: int
    stage_id: uuid.UUID
    position: float
    title: str
    priority: BUDPriority | None
    start_at: datetime | None
    due_at: datetime | None
    due_done: bool
    archived_at: datetime | None
    updated_at: datetime
    assignee_ids: list[uuid.UUID]
    label_ids: list[uuid.UUID]
    checklist_done: int
    checklist_total: int
    has_description: bool
    has_prd: bool
    repo_id: uuid.UUID | None
    handovers: list[HandoverChip] = Field(default_factory=list)
    delivery: CardDelivery = CardDelivery.NONE
    agent_run: CardAgentRun | None = None


class CardPage(BaseModel):
    """One page of cards; pass ``next_cursor`` back as ``cursor`` for the next.

    ``next_cursor`` is ``None`` on the last page.
    """

    items: list[CardSummary]
    next_cursor: str | None


class CardDetail(CardSummary):
    """One card with everything its page shows above the threads."""

    board_key: str
    description_md: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_by: uuid.UUID | None
    created_at: datetime
