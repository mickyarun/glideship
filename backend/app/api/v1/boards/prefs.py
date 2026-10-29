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

"""My star and saved filters for a board; viewers have them too."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.boards._access import read_board
from app.core.deps import get_db
from app.schemas.boards.prefs import BoardFilters, PrefsRead, StarBody
from app.services.boards import prefs_service
from app.services.boards.access import BoardAccess

router = APIRouter(tags=["boards"])


@router.get("/{key}/prefs", response_model=PrefsRead)
async def read_prefs(
    access: BoardAccess = Depends(read_board), db: AsyncSession = Depends(get_db)
) -> PrefsRead:
    """My star and saved filters for this board."""
    return await prefs_service.read_prefs(db, access)


@router.put("/{key}/star", response_model=PrefsRead)
async def set_star(
    body: StarBody,
    access: BoardAccess = Depends(read_board),
    db: AsyncSession = Depends(get_db),
) -> PrefsRead:
    """Star or unstar this board for me."""
    return await prefs_service.set_star(db, access, starred=body.starred)


@router.put("/{key}/prefs", response_model=PrefsRead)
async def set_filters(
    body: BoardFilters,
    access: BoardAccess = Depends(read_board),
    db: AsyncSession = Depends(get_db),
) -> PrefsRead:
    """Save the filters to restore when I come back to this board."""
    return await prefs_service.set_filters(db, access, body)
