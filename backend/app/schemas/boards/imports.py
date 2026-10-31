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

"""Import sessions over HTTP, and the org's Trello credentials."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.external_import import ExternalImportStatus, ImportMode, ImportSourceKind
from app.schemas.boards.import_mapping import ImportMapping
from app.schemas.boards.trello_discovery import TrelloDiscovery

# Trello board ids are 24 hex characters; short links are 8 letters and digits.
TRELLO_BOARD_REF = r"^[0-9A-Za-z]{8,24}$"
CREDENTIAL_MAX_LENGTH = 512


class ImportAccepted(BaseModel):
    """A queued import job (202): follow it on ``job:<jobId>``."""

    model_config = ConfigDict(populate_by_name=True)

    job_id: str = Field(alias="jobId")
    session_id: uuid.UUID = Field(alias="sessionId")


class TrelloApiImportCreate(BaseModel):
    """Start an import from the Trello API instead of an uploaded export."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["api"]
    trello_board_id: str = Field(pattern=TRELLO_BOARD_REF)


class ImportResult(BaseModel):
    """What a finished (or interrupted) run did."""

    imported: int = 0
    skipped: int = 0
    failed: int = 0
    already_imported: int = 0
    dropped: dict[str, int] = Field(default_factory=dict)


class ImportSessionRead(BaseModel):
    """An import session as the review and progress screens show it."""

    id: uuid.UUID
    source_kind: ImportSourceKind
    mode: ImportMode
    status: ExternalImportStatus
    board_id: uuid.UUID | None
    board_key: str | None
    total_cards: int | None
    processed_count: int
    last_processed_index: int | None
    job_id: str | None
    error: str | None
    discovery: TrelloDiscovery | None
    mapping: ImportMapping | None
    result: ImportResult | None
    created_at: datetime
    updated_at: datetime


class TrelloBoardOption(BaseModel):
    """One of the connected Trello member's open boards, for the picker."""

    id: str
    name: str
    url: str | None = None


class TrelloCredentialsWrite(BaseModel):
    """A Trello API key and a read-scoped token; stored encrypted, never returned."""

    model_config = ConfigDict(extra="forbid")

    api_key: str = Field(min_length=1, max_length=CREDENTIAL_MAX_LENGTH)
    token: str = Field(min_length=1, max_length=CREDENTIAL_MAX_LENGTH)


class TrelloSettingsRead(BaseModel):
    """Whether Trello is connected, and as whom; never the key or token."""

    configured: bool
    member_username: str | None = None
    connected_at: datetime | None = None
