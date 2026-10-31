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

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.board_people import BoardPeopleRepository
from app.schemas.boards.people import BoardPeopleRead, BoardPersonRead
from app.services.boards.access import BoardAccess


async def list_people(db: AsyncSession, access: BoardAccess) -> BoardPeopleRead:
    """Everyone with a role on the board, by name, with their highest role."""
    rows = await BoardPeopleRepository(db, org_id=access.org_id).list_people(access.board.id)
    return BoardPeopleRead(
        items=[
            BoardPersonRead(
                id=row.id, name=row.name, avatar_url=row.avatar_url, role=row.role, via=row.via
            )
            for row in rows
        ]
    )
