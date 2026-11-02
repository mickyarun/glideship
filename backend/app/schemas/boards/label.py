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

"""Board labels."""

import uuid

from pydantic import BaseModel, ConfigDict

from app.models.board_enums import BoardLabelColor
from app.schemas.boards.text import LabelName


class LabelCreate(BaseModel):
    """A new label; names are unique per board."""

    model_config = ConfigDict(extra="forbid")

    name: LabelName
    color: BoardLabelColor


class LabelUpdate(BaseModel):
    """Label edits; omitted fields stay."""

    model_config = ConfigDict(extra="forbid")

    name: LabelName | None = None
    color: BoardLabelColor | None = None


class LabelRead(BaseModel):
    """One label."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    color: BoardLabelColor
