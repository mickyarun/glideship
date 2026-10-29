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

"""Boards: creating, listing, reading and editing one."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.board_enums import BoardMemberRole, BoardStatus, BoardVisibility
from app.models.bud import BUDStatus
from app.schemas.boards.label import LabelRead
from app.schemas.boards.stage import StageRead
from app.schemas.boards.text import BoardDescription, BoardName
from app.services.boards.board_template import TemplateStage
from app.services.boards.constants import BOARD_KEY_MAX_LENGTH, BoardAction


class BoardCreate(BaseModel):
    """A new board from a template; the key can't change afterwards."""

    model_config = ConfigDict(extra="forbid")

    name: BoardName
    key: str = Field(min_length=1, max_length=BOARD_KEY_MAX_LENGTH)
    template: str = Field(min_length=1)
    visibility: BoardVisibility = BoardVisibility.ORG
    description: BoardDescription | None = None


class BoardUpdate(BaseModel):
    """Board settings; omitted fields stay as they are."""

    model_config = ConfigDict(extra="forbid")

    name: BoardName | None = None
    description: BoardDescription | None = None
    visibility: BoardVisibility | None = None
    handover_enabled: bool | None = None
    handover_stage_id: uuid.UUID | None = None
    return_stage_id: uuid.UUID | None = None
    handover_target_status: BUDStatus | None = None
    ai_enabled: bool | None = None


class BoardRead(BaseModel):
    """A board's settings."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    name: str
    description: str | None
    status: BoardStatus
    visibility: BoardVisibility
    handover_enabled: bool
    handover_stage_id: uuid.UUID | None
    return_stage_id: uuid.UUID | None
    handover_target_status: BUDStatus
    ai_enabled: bool
    created_at: datetime
    updated_at: datetime


class BoardDetail(BaseModel):
    """A board as its page loads it: settings, stages, labels and what I may do."""

    board: BoardRead
    stages: list[StageRead]
    labels: list[LabelRead]
    role: BoardMemberRole
    capabilities: list[BoardAction]
    starred: bool


class CustomBoardItem(BaseModel):
    """A team board in the boards list."""

    kind: Literal["custom"] = "custom"
    id: uuid.UUID
    key: str
    name: str
    visibility: BoardVisibility
    role: BoardMemberRole
    starred: bool


class DeliveryBoardItem(BaseModel):
    """The BUD board, listed beside team boards for engineering members."""

    kind: Literal["delivery"] = "delivery"
    name: str
    path: str


BoardListItem = Annotated[CustomBoardItem | DeliveryBoardItem, Field(discriminator="kind")]


class BoardList(BaseModel):
    """Every board I can open, then the Delivery board when I can see it."""

    items: list[BoardListItem]


class TemplateRead(BaseModel):
    """A board template a new board can start from."""

    id: str
    name: str
    description: str
    stages: list[TemplateStage]
    handover_stage: str | None
    return_stage: str | None
