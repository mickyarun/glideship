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

"""Card documents and their versions."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.board_enums import BoardCardDocKind, BoardCardDocState
from app.models.bud_version import BUDEditSource
from app.schemas.boards.text import DocText


class DocWrite(BaseModel):
    """A new current version of one document.

    ``base_version`` is the version the edit started from (``null`` for a
    document that doesn't exist yet); a different current version is 409.
    """

    model_config = ConfigDict(extra="forbid")

    body_md: DocText
    base_version: int | None


class DocRestore(BaseModel):
    """Restore an old version over the current one, which must be ``base_version``."""

    model_config = ConfigDict(extra="forbid")

    base_version: int | None


class DocVersionRead(BaseModel):
    """One version of one document, without its text."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: BoardCardDocKind
    state: BoardCardDocState
    version: int
    source: BUDEditSource
    # The stage-agent run that wrote it, and who accepted or rejected a draft.
    agent_run_id: uuid.UUID | None = None
    created_by: uuid.UUID | None
    reviewed_by: uuid.UUID | None = None
    reviewed_at: datetime | None = None
    created_at: datetime


class DocRead(DocVersionRead):
    """One version of one document, with its text."""

    body_md: str


class DocVersionPage(BaseModel):
    """Newest first; pass ``next_before`` back as ``before`` for older versions."""

    items: list[DocVersionRead]
    next_before: int | None


class DocList(BaseModel):
    """The current version of each document on a card, and the drafts awaiting review.

    ``drafts`` are ``pending_review`` versions an agent wrote, newest first;
    none of them is part of the card until someone accepts it.
    """

    items: list[DocRead]
    drafts: list[DocRead] = []
