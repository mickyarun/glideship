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

"""What parsing a Trello board found, as the review screen reads it."""

import uuid
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel

from app.models.board_enums import BoardLabelColor, BoardStageCategory


class TrelloWarning(StrEnum):
    """Things the review screen should point out before the import starts."""

    # The export holds only the newest 1,000 actions, so older comments are
    # missing; API mode fetches them all.
    ACTION_CAP = "action_cap"


class DiscoveredList(BaseModel):
    """A Trello list and the stage we'd suggest for it."""

    id: str
    name: str
    closed: bool
    card_count: int
    # Of ``card_count``, the cards archived in Trello (``closed``).
    archived_card_count: int
    suggested_name: str
    suggested_category: BoardStageCategory
    # Archived lists are skipped unless the reviewer says otherwise.
    suggested_skip: bool


class DiscoveredLabel(BaseModel):
    """A Trello label and the board label colour it maps to."""

    id: str
    name: str
    color: str | None
    mapped_color: BoardLabelColor


class DiscoveredMember(BaseModel):
    """A Trello member, with the org member whose full name matches, if exactly one does."""

    id: str
    full_name: str
    username: str
    suggested_user_id: uuid.UUID | None


class DiscoveryCounts(BaseModel):
    """How much the board holds."""

    cards: int
    archived_cards: int
    comments: int
    checklist_items: int
    attachments: int
    actions: int


class DroppedCounts(BaseModel):
    """What the import can't carry over; the review screen says so."""

    custom_fields: int
    power_up_data: int
    covers: int


class TrelloDiscovery(BaseModel):
    """The parse result stored on the session; ``board_url`` is a checked http(s) link."""

    source_kind: Literal["trello"] = "trello"
    board_id: str
    board_name: str
    board_url: str | None
    lists: list[DiscoveredList]
    labels: list[DiscoveredLabel]
    members: list[DiscoveredMember]
    counts: DiscoveryCounts
    dropped: DroppedCounts
    warnings: list[TrelloWarning]
