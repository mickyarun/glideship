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

"""Everyone who can open a board, for the assignee picker."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.boards._access import view_board
from app.core.deps import get_db
from app.schemas.boards.people import BoardPeopleRead
from app.services.boards import people_service
from app.services.boards.access import BoardAccess

router = APIRouter(tags=["boards"])


@router.get("/{key}/people", response_model=BoardPeopleRead)
async def list_people(
    access: BoardAccess = Depends(view_board), db: AsyncSession = Depends(get_db)
) -> BoardPeopleRead:
    """Everyone with a role on the board: exactly who its cards can be assigned to."""
    return await people_service.list_people(db, access)
