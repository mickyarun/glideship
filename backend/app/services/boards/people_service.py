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

"""Everyone who can open a board: the people its cards can be assigned to."""

import uuid
from collections.abc import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.board_member import BoardMemberRepository
from app.repositories.board_people import BoardPeopleRepository
from app.schemas.boards.people import BoardPeopleRead, BoardPersonRead
from app.services.boards.access import BoardAccess
from app.services.boards.live import BoardChanges, BoardSocketEvent


async def list_people(db: AsyncSession, access: BoardAccess) -> BoardPeopleRead:
    """Everyone with a role on the board, by name, with their highest role."""
    rows = await BoardPeopleRepository(db, org_id=access.org_id).list_people(access.board.id)
    return BoardPeopleRead(
        items=[
            BoardPersonRead(
                id=row.id,
                name=row.name,
                avatar_url=row.avatar_url,
                role=row.role,
                via=row.via,
                team_name=row.team_name,
            )
            for row in rows
        ]
    )


async def team_people_changed(
    db: AsyncSession,
    org_id: uuid.UUID,
    team_id: uuid.UUID,
    *,
    losing: Iterable[uuid.UUID] = (),
) -> None:
    """Tell every board that gives the team a role that its people changed.

    Call it in the transaction that changes the team's people or status;
    each board hears ``people_changed`` when it commits. ``losing`` are the
    people who may lose access through this change: they don't hear it, and
    their sockets on those boards re-check.
    """
    gone = set(losing)
    for board_id in await BoardMemberRepository(db, org_id=org_id).boards_granting_team(team_id):
        changes = BoardChanges(board_id, actor_id=None)
        changes.emit(BoardSocketEvent.PEOPLE_CHANGED)
        if gone:
            changes.recheck_access(gone)
        changes.queue(db)
