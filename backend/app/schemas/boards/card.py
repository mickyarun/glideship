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

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.models.bud import BUDPriority
from app.schemas.boards.text import CardTitle, Description, IdList


class CardCreate(BaseModel):
    """A new card, at the bottom of ``stage_id`` or of the default stage."""

    model_config = ConfigDict(extra="forbid")

    title: CardTitle
    description_md: Description | None = None
    stage_id: uuid.UUID | None = None
    priority: BUDPriority | None = None
    start_at: AwareDatetime | None = None
    due_at: AwareDatetime | None = None
    assignee_ids: IdList = Field(default_factory=list)
    label_ids: IdList = Field(default_factory=list)


class CardUpdate(BaseModel):
    """Card edits. Omitted fields stay; ``null`` clears a nullable field."""

    model_config = ConfigDict(extra="forbid")

    title: CardTitle | None = None
    description_md: Description | None = None
    priority: BUDPriority | None = None
    start_at: AwareDatetime | None = None
    due_at: AwareDatetime | None = None
    due_done: bool | None = None
    assignee_ids: IdList | None = None
    label_ids: IdList | None = None


class CardMove(BaseModel):
    """Where a card goes on its board: after one card and/or before another.

    With neither neighbour the card goes to the bottom of the stage.
    """

    model_config = ConfigDict(extra="forbid")

    stage_id: uuid.UUID
    after_id: uuid.UUID | None = None
    before_id: uuid.UUID | None = None


class HandoverChip(BaseModel):
    """A BUD this card was handed over to (filled in once handover ships)."""

    bud_id: uuid.UUID
    status: str


class CardSummary(BaseModel):
    """A card as a board column shows it."""

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
    handovers: list[HandoverChip] = Field(default_factory=list)


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
