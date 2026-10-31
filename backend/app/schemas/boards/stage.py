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

"""Board stages: the columns, their categories, WIP limits and order."""

import uuid
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.models.board_enums import BoardStageCategory, StageRequiredField
from app.schemas.boards.text import OrderList, StageName
from app.services.boards.constants import WIP_LIMIT_MAX


def _no_repeats(fields: list[StageRequiredField]) -> list[StageRequiredField]:
    if len(set(fields)) != len(fields):
        raise ValueError("List each required field once.")
    return fields


# What a card must have to enter the stage; each field at most once.
RequiredFields = Annotated[
    list[StageRequiredField],
    Field(max_length=len(StageRequiredField)),
    AfterValidator(_no_repeats),
]


class StageCreate(BaseModel):
    """A new stage, added at the right-hand end."""

    model_config = ConfigDict(extra="forbid")

    name: StageName
    category: BoardStageCategory
    wip_limit: int | None = Field(default=None, gt=0, le=WIP_LIMIT_MAX)
    is_default: bool = False
    required_fields: RequiredFields = Field(default_factory=list)


class StageUpdate(BaseModel):
    """Stage settings; omitted fields stay. Send ``wip_limit: null`` to clear it.

    ``required_fields`` replaces the whole list; send ``[]`` to require nothing.
    """

    model_config = ConfigDict(extra="forbid")

    name: StageName | None = None
    category: BoardStageCategory | None = None
    wip_limit: int | None = Field(default=None, gt=0, le=WIP_LIMIT_MAX)
    is_default: bool | None = None
    required_fields: RequiredFields | None = None


class StageOrder(BaseModel):
    """Every stage of the board, left to right."""

    model_config = ConfigDict(extra="forbid")

    stage_ids: OrderList


class StageRead(BaseModel):
    """One stage, with how many open cards it holds."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    category: BoardStageCategory
    position: int
    wip_limit: int | None
    is_default: bool
    required_fields: list[StageRequiredField]
    open_cards: int = 0
