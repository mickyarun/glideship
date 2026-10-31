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

"""What hangs off a card: its checklist, comments, attachments and history."""

import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, UrlConstraints

from app.models.board_card_detail import ATTACHMENT_URL_LENGTH, CHECKLIST_GROUP_LENGTH
from app.models.board_enums import BoardAttachmentKind, BoardCardEventType, BoardStageCategory
from app.models.external_import import ImportSourceKind
from app.models.thread_columns import ATTACHMENT_FILENAME_LENGTH
from app.schemas.boards.text import ChecklistOrderList, ChecklistText, CommentText


class ChecklistItemCreate(BaseModel):
    """A new checklist line, added at the bottom."""

    model_config = ConfigDict(extra="forbid")

    text: ChecklistText
    group_name: str | None = Field(default=None, max_length=CHECKLIST_GROUP_LENGTH)


class ChecklistItemUpdate(BaseModel):
    """Checklist line edits; omitted fields stay."""

    model_config = ConfigDict(extra="forbid")

    text: ChecklistText | None = None
    done: bool | None = None
    group_name: str | None = Field(default=None, max_length=CHECKLIST_GROUP_LENGTH)


class ChecklistOrder(BaseModel):
    """Every checklist item of the card, top to bottom."""

    model_config = ConfigDict(extra="forbid")

    item_ids: ChecklistOrderList


class ChecklistItemRead(BaseModel):
    """One checklist line."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    text: str
    done: bool
    group_name: str | None
    position: float


class CommentBody(BaseModel):
    """A comment's text, for a new comment or an edit."""

    model_config = ConfigDict(extra="forbid")

    body: CommentText


class CommentRead(BaseModel):
    """One comment; a deleted one keeps its place with an empty body."""

    id: uuid.UUID
    author_id: uuid.UUID | None
    author_label: str | None
    author_name: str | None
    author_avatar_url: str | None
    body: str
    # Where an imported comment came from (e.g. ``trello``); None when written here.
    import_source: ImportSourceKind | None
    edited_at: datetime | None
    deleted_at: datetime | None
    created_at: datetime


class CommentPage(BaseModel):
    """Oldest first; pass ``next_cursor`` back as ``cursor`` for the next page."""

    items: list[CommentRead]
    next_cursor: str | None


class LinkCreate(BaseModel):
    """A link attached to a card."""

    model_config = ConfigDict(extra="forbid")

    url: Annotated[AnyHttpUrl, UrlConstraints(max_length=ATTACHMENT_URL_LENGTH)]
    title: str | None = Field(default=None, min_length=1, max_length=ATTACHMENT_FILENAME_LENGTH)


class AttachmentRead(BaseModel):
    """A file (download it by id) or a link on a card."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: BoardAttachmentKind
    filename: str
    url: str | None
    mime_type: str | None
    size_bytes: int | None
    uploaded_by: uuid.UUID | None
    created_at: datetime


class AttachmentLimits(BaseModel):
    """What a card accepts, for the picker to check before uploading."""

    max_file_mb: int
    max_files: int
    accepted_extensions: list[str]


class AttachmentList(BaseModel):
    """A card's files and links, with the limits."""

    items: list[AttachmentRead]
    limits: AttachmentLimits


class EventRead(BaseModel):
    """One entry in a card's history."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: BoardCardEventType
    board_id: uuid.UUID
    actor_id: uuid.UUID | None
    actor_label: str | None
    from_stage_id: uuid.UUID | None
    to_stage_id: uuid.UUID | None
    from_category: BoardStageCategory | None
    to_category: BoardStageCategory | None
    detail: dict[str, Any]
    created_at: datetime


class EventPage(BaseModel):
    """Newest first; pass ``next_before`` as ``before`` for older entries."""

    items: list[EventRead]
    next_before: uuid.UUID | None
