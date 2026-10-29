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

"""The filters a person saves per board, restored when they come back to it."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.config import settings
from app.models.bud import BUDPriority
from app.schemas.boards.text import SEARCH_MAX_LENGTH, IdList


class BoardFilters(BaseModel):
    """The board filters to restore when someone comes back to a board.

    Stored as JSON on their prefs row, so the whole set is capped at
    ``BoardsConfig.filters_max_bytes``.
    """

    model_config = ConfigDict(extra="forbid")

    q: str | None = Field(default=None, max_length=SEARCH_MAX_LENGTH)
    assignee_ids: IdList = Field(default_factory=list)
    label_ids: IdList = Field(default_factory=list)
    priorities: list[BUDPriority] = Field(default_factory=list)
    archived: bool = False

    @model_validator(mode="after")
    def _fits(self) -> Self:
        limit = settings.boards.filters_max_bytes
        if len(self.model_dump_json().encode()) > limit:
            raise ValueError(f"saved filters are limited to {limit} bytes")
        return self


def saved_filters(raw: object) -> BoardFilters:
    """Filters as stored on a prefs row; none when unset or saved under looser limits."""
    if raw is None:
        return BoardFilters()
    try:
        return BoardFilters.model_validate(raw)
    except ValidationError:
        return BoardFilters()
