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

"""The reviewed shape of an import: where it goes and how source groups become stages.

The vocabulary is the source's neutral one: a *group* is whatever the
source sorts cards into (a Trello list), a *member* is a source person.
The same model is stored on the session as ``config``, so the import job
reads exactly what the review screen saved.
"""

import uuid
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.config_board_imports import IMPORT_MAPPING_MAX_ENTRIES
from app.models.board_enums import BoardStageCategory, BoardVisibility
from app.models.external_import import EXTERNAL_ID_LENGTH
from app.schemas.boards.text import BoardDescription, BoardName, StageName
from app.services.boards.constants import BOARD_KEY_MAX_LENGTH

# Groups and members one mapping may name; far above a real board.
MAPPING_MAX_ENTRIES = IMPORT_MAPPING_MAX_ENTRIES

ExternalId = Annotated[str, Field(min_length=1, max_length=EXTERNAL_ID_LENGTH)]


class StageChoice(StrEnum):
    """What a source group becomes."""

    NEW = "new"
    EXISTING = "existing"
    SKIP = "skip"


class ArchivedChoice(StrEnum):
    """What happens to cards archived in the source."""

    SKIP = "skip"
    ARCHIVE = "archive"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NewBoardTarget(_Strict):
    """Import into a board made for it; checked like ``POST /boards``."""

    kind: Literal["new"] = "new"
    name: BoardName
    key: str = Field(min_length=1, max_length=BOARD_KEY_MAX_LENGTH)
    visibility: BoardVisibility = BoardVisibility.ORG
    description: BoardDescription | None = None


class ExistingBoardTarget(_Strict):
    """Import into a board the caller is admin on."""

    kind: Literal["existing"] = "existing"
    key: str = Field(min_length=1, max_length=BOARD_KEY_MAX_LENGTH)


ImportTarget = Annotated[NewBoardTarget | ExistingBoardTarget, Field(discriminator="kind")]


class GroupMapping(_Strict):
    """One source group: a new stage (groups may share one), an existing stage, or skipped."""

    group_id: ExternalId
    action: StageChoice
    name: StageName | None = None
    category: BoardStageCategory | None = None
    stage_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _fields_match_action(self) -> Self:
        if self.action is StageChoice.NEW and (self.name is None or self.category is None):
            raise ValueError("A new stage needs a name and a category.")
        if self.action is StageChoice.EXISTING and self.stage_id is None:
            raise ValueError("Pick the existing stage this group goes into.")
        return self


class MemberMapping(_Strict):
    """A source member and the org member they are, or None for nobody."""

    member_id: ExternalId
    user_id: uuid.UUID | None = None


class ImportMapping(_Strict):
    """Everything the reviewer decided before starting the import."""

    target: ImportTarget
    groups: list[GroupMapping] = Field(max_length=MAPPING_MAX_ENTRIES)
    members: list[MemberMapping] = Field(default_factory=list, max_length=MAPPING_MAX_ENTRIES)
    archived_cards: ArchivedChoice = ArchivedChoice.SKIP

    def user_for(self) -> dict[str, uuid.UUID]:
        """Source member id → user id, for members mapped to someone."""
        return {m.member_id: m.user_id for m in self.members if m.user_id is not None}
