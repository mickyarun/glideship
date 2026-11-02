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


"""The target board shaped for one import: its stages, people and labels.

Everything here finds before it makes, so a resumed run reuses what the
first run created. People mapped onto a new board become its editors, as
they were members of the source board; on any board, someone who has
since lost access is left unmapped rather than assigned. Labels match the
board's by name ignoring case, so source labels differing only in case
share one board label, keeping the colour of the first.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from app.core.permissions_boards import BOARDS_VIEW
from app.models.board import BoardLabel, BoardStage
from app.models.board_enums import BoardMemberRole
from app.repositories.board_access import BoardAccessRepository
from app.repositories.board_label import BoardLabelRepository
from app.repositories.board_member import BoardMemberRepository
from app.repositories.import_people import ImportPeopleRepository
from app.schemas.boards.import_mapping import ImportMapping, NewBoardTarget
from app.services.imports.context import ImportContext
from app.services.imports.draft import LabelDraft
from app.services.imports.stage_plan import ensure_stages, stage_key


@dataclass(frozen=True)
class BoardPlan:
    """Source ids → what they became on the board."""

    stages: dict[str, BoardStage]
    users: dict[str, uuid.UUID]
    labels: dict[str, uuid.UUID]


async def build_plan(
    ctx: ImportContext, mapping: ImportMapping, labels: Sequence[LabelDraft]
) -> BoardPlan:
    """Make the board ready for the cards; the caller commits."""
    new_board = isinstance(mapping.target, NewBoardTarget)
    stages = await ensure_stages(ctx.db, ctx.board, mapping, new_board=new_board)
    return BoardPlan(
        stages=stages,
        users=await _users(ctx, mapping, new_board=new_board),
        labels=await _labels(ctx, labels),
    )


async def _users(
    ctx: ImportContext, mapping: ImportMapping, *, new_board: bool
) -> dict[str, uuid.UUID]:
    mapped = mapping.user_for()
    wanted = set(mapped.values())
    if new_board:
        people = ImportPeopleRepository(ctx.db, org_id=ctx.org_id)
        members = BoardMemberRepository(ctx.db, org_id=ctx.org_id)
        for user_id in await people.active_holding(wanted - {ctx.actor_id}, BOARDS_VIEW):
            if await members.member_role(ctx.board.id, user_id) is None:
                await members.put_member(ctx.board.id, user_id, BoardMemberRole.EDITOR)
    access = BoardAccessRepository(ctx.db, org_id=ctx.org_id)
    allowed = await access.users_with_access(ctx.board.id, wanted)
    lost = {m for m, u in mapped.items() if u not in allowed}
    # Set, not added: a resumed run checks everyone again.
    ctx.counters["members_without_access"] = len(lost)
    return {m: u for m, u in mapped.items() if u in allowed}


async def _labels(ctx: ImportContext, labels: Sequence[LabelDraft]) -> dict[str, uuid.UUID]:
    repo = BoardLabelRepository(ctx.db, org_id=ctx.org_id)
    by_name = {
        stage_key(label.name): label.id for label in await repo.list_for_board(ctx.board.id)
    }
    resolved: dict[str, uuid.UUID] = {}
    for draft in labels:
        found = by_name.get(stage_key(draft.name))
        if found is None:
            label = BoardLabel(
                org_id=ctx.org_id, board_id=ctx.board.id, name=draft.name, color=draft.color
            )
            if not await repo.save(label):
                # Someone added the same name a moment ago; use theirs.
                again = {stage_key(x.name): x.id for x in await repo.list_for_board(ctx.board.id)}
                found = again[stage_key(draft.name)]
            else:
                found = label.id
            by_name[stage_key(draft.name)] = found
        resolved[draft.id] = found
    return resolved
