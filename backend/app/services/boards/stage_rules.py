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

"""The rules every board's stage set keeps, checked after each change.

A board has at least one ``todo`` and one ``done`` stage, exactly one
default stage, no more than ``BoardsConfig.max_stages_per_board`` stages,
and its handover and return stages keep the categories handover needs.
The template validator checks the same shape for new boards.
"""

import uuid
from collections.abc import Sequence
from typing import Protocol

from app.config import settings
from app.models.board_enums import BoardStageCategory
from app.services.boards.errors import BoardRuleError


class StageShape(Protocol):
    """The parts of a stage the rules look at."""

    @property
    def id(self) -> uuid.UUID:
        """The stage's id."""
        ...

    @property
    def category(self) -> BoardStageCategory:
        """The stage's category."""
        ...

    @property
    def is_default(self) -> bool:
        """Whether new cards land here."""
        ...


def check_stage_count(count: int) -> None:
    """Refuse a stage set larger than the board limit."""
    limit = settings.boards.max_stages_per_board
    if count > limit:
        raise BoardRuleError(f"A board can have at most {limit} stages.")


def check_stages(
    stages: Sequence[StageShape],
    *,
    handover_stage_id: uuid.UUID | None,
    return_stage_id: uuid.UUID | None,
) -> None:
    """Raise :class:`BoardRuleError` when the stage set breaks a board rule."""
    check_stage_count(len(stages))
    categories = {s.category for s in stages}
    for needed in (BoardStageCategory.TODO, BoardStageCategory.DONE):
        if needed not in categories:
            raise BoardRuleError(f"A board needs at least one {needed.value} stage.")
    if sum(s.is_default for s in stages) != 1:
        raise BoardRuleError("Exactly one stage must be where new cards land.")
    by_id = {s.id: s for s in stages}
    _check_named(by_id, handover_stage_id, BoardStageCategory.DONE, "handover")
    _check_named(by_id, return_stage_id, BoardStageCategory.TODO, "return")


def _check_named(
    by_id: dict[uuid.UUID, StageShape],
    stage_id: uuid.UUID | None,
    category: BoardStageCategory,
    role: str,
) -> None:
    if stage_id is None:
        return
    stage = by_id.get(stage_id)
    if stage is None:
        raise BoardRuleError(f"The {role} stage must be one of this board's stages.")
    if stage.category is not category:
        raise BoardRuleError(f"The {role} stage must be a {category.value} stage.")
