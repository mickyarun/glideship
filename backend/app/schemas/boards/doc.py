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
    """A new current version of one document."""

    model_config = ConfigDict(extra="forbid")

    body_md: DocText


class DocRead(BaseModel):
    """One version of one document."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: BoardCardDocKind
    state: BoardCardDocState
    version: int
    body_md: str
    source: BUDEditSource
    created_by: uuid.UUID | None
    created_at: datetime


class DocList(BaseModel):
    """The current version of each document on a card."""

    items: list[DocRead]
