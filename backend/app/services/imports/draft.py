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


"""What a source hands the shared writer: one draft per card, and its labels.

A source turns its own data into these, already cleaned and cut to our
column and product limits; the shared writer only maps ids through the
reviewed mapping and stores them. ``external_id`` values are the source's
own and only need to be unique within that source: the item maps are
keyed by source kind, so namespacing ids is each source's job.
"""

from dataclasses import dataclass, field
from datetime import datetime

from app.models.board_enums import BoardLabelColor


@dataclass(frozen=True)
class ChecklistLine:
    """One checklist item, with the group (checklist) it came from."""

    group: str | None
    text: str
    done: bool


@dataclass(frozen=True)
class CommentDraft:
    """A comment with its original date; ``author_label`` names an unmapped author."""

    at: datetime | None
    member_id: str
    author_label: str
    text: str


@dataclass(frozen=True)
class AttachmentDraft:
    """A link, or (``is_upload``) a file the source holds that API mode may copy."""

    id: str
    name: str
    url: str
    is_upload: bool


@dataclass(frozen=True)
class LabelDraft:
    """A source label as it lands on the board."""

    id: str
    name: str
    color: BoardLabelColor


@dataclass
class CardDraft:
    """Everything one card brings, before it's mapped onto a board.

    ``group_id`` is the source group (a Trello list) the mapping turns into
    a stage. ``source_key`` and ``url`` go on the card's ``imported`` event;
    ``url`` is a checked http(s) link or None.
    """

    id: str
    group_id: str
    title: str
    description: str | None
    closed: bool
    start_at: datetime | None
    due_at: datetime | None
    due_done: bool
    member_ids: list[str]
    label_ids: list[str]
    source_key: str
    url: str | None
    checklist: list[ChecklistLine] = field(default_factory=list)
    comments: list[CommentDraft] = field(default_factory=list)
    attachments: list[AttachmentDraft] = field(default_factory=list)
    # What this card carries that the import drops or cuts, by kind.
    dropped: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceBoard:
    """A parsed source, as the import job writes it: cards in a stable order, and labels."""

    cards: list[CardDraft]
    labels: list[LabelDraft]
