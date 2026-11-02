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

"""The stages a mapping adds, and finding or making them on the board.

Several source groups may name the same new stage (compared ignoring
case); they then share it, and must agree on its category. On a new board
the first ``todo`` stage is where new cards land.
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board import Board, BoardStage
from app.models.board_enums import BoardStageCategory
from app.repositories.board_stage import BoardStageRepository
from app.schemas.boards.import_mapping import ImportMapping, StageChoice
from app.services.boards.errors import BoardErrorCode, BoardRuleError
from app.services.boards.stage_rules import check_stage_count, check_stages
from app.services.imports.errors import ImportStateError

STAGE_GONE = "A stage this import maps cards into is no longer on the board. Review it again."


@dataclass(frozen=True)
class PlannedStage:
    """A stage the mapping asks for, shaped for the stage rules."""

    name: str
    category: BoardStageCategory
    is_default: bool = False
    id: uuid.UUID = field(default_factory=uuid.uuid4)


def stage_key(name: str) -> str:
    """How stage names are compared: case and outer spaces ignored."""
    return name.strip().casefold()


def planned_stages(mapping: ImportMapping, *, new_board: bool) -> list[PlannedStage]:
    """The distinct new stages, in list order.

    Raises:
        BoardRuleError: Two groups name one stage with different categories.
    """
    by_key: dict[str, PlannedStage] = {}
    for entry in mapping.groups:
        if entry.action is not StageChoice.NEW:
            continue
        assert entry.name is not None and entry.category is not None
        found = by_key.get(stage_key(entry.name))
        if found is None:
            by_key[stage_key(entry.name)] = PlannedStage(entry.name, entry.category)
        elif found.category is not entry.category:
            raise BoardRuleError(f"Everything going into {entry.name!r} must share one category.")
    stages = list(by_key.values())
    if new_board:
        first_todo = next((s for s in stages if s.category is BoardStageCategory.TODO), None)
        stages = [
            PlannedStage(s.name, s.category, is_default=s is first_todo, id=s.id) for s in stages
        ]
        check_stages(stages, handover_stage_id=None, return_stage_id=None)
    return stages


async def ensure_stages(
    db: AsyncSession, board: Board, mapping: ImportMapping, *, new_board: bool
) -> dict[str, BoardStage]:
    """Source group id → its stage, making missing new stages; groups skipped are absent.

    Idempotent: a stage that already exists by name is reused, so a resumed
    import doesn't add it twice.

    Raises:
        ImportStateError: A mapped existing stage was deleted since.
        BoardRuleError: The board would break a stage rule.
    """
    repo = BoardStageRepository(db, org_id=board.org_id)
    stages = await repo.lock_board_stages(board.id)
    by_name = {stage_key(s.name): s for s in stages}
    by_id = {s.id: s for s in stages}
    check_mapped_stages(mapping, by_id.keys())
    planned = planned_stages(mapping, new_board=new_board)
    missing = [p for p in planned if stage_key(p.name) not in by_name]
    check_stage_count(len(stages) + len(missing))
    position = max((s.position for s in stages), default=-1)
    has_default = any(s.is_default for s in stages)
    for plan in missing:
        position += 1
        stage = BoardStage(
            org_id=board.org_id,
            board_id=board.id,
            name=plan.name,
            category=plan.category,
            position=position,
            is_default=plan.is_default and not has_default,
        )
        await repo.add(stage)
        by_name[stage_key(plan.name)] = stage
    await repo.flush()
    resolved: dict[str, BoardStage] = {}
    for entry in mapping.groups:
        if entry.action is StageChoice.NEW:
            assert entry.name is not None
            resolved[entry.group_id] = by_name[stage_key(entry.name)]
        elif entry.action is StageChoice.EXISTING:
            assert entry.stage_id is not None
            resolved[entry.group_id] = by_id[entry.stage_id]
    return resolved


def check_mapped_stages(mapping: ImportMapping, stage_ids: Iterable[uuid.UUID]) -> None:
    """Refuse a mapping whose existing stages aren't all still on the board.

    Raises:
        ImportStateError: One was deleted since the review.
    """
    present = set(stage_ids)
    if any(e.action is StageChoice.EXISTING and e.stage_id not in present for e in mapping.groups):
        raise ImportStateError(STAGE_GONE, code=BoardErrorCode.STAGE_GONE)
