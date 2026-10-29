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

"""My star and saved filters per board, and the board switcher.

Prefs are personal, so they can be saved on an archived board and by viewers.
"""

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.repositories.board import VisibleBoard
from app.repositories.board_prefs import BoardPrefsRepository
from app.repositories.board_switcher import BoardSwitcherRepository
from app.schemas.boards.board import DeliveryBoardItem
from app.schemas.boards.prefs import BoardFilters, PrefsRead, SwitcherBoard, SwitcherRead
from app.services.boards.access import BoardAccess, BoardCaller
from app.services.boards.board_service import delivery_item


async def read_prefs(db: AsyncSession, access: BoardAccess) -> PrefsRead:
    """My star and filters for the board (defaults when I've saved none)."""
    row = await BoardPrefsRepository(db, org_id=access.org_id).get(access.board.id, access.user_id)
    if row is None:
        return PrefsRead(starred=False, filters=BoardFilters())
    try:
        filters = BoardFilters.model_validate(row.filters)
    except ValidationError:
        # Saved under looser limits than today's; start from no filters.
        filters = BoardFilters()
    return PrefsRead(starred=row.starred, filters=filters)


async def set_star(db: AsyncSession, access: BoardAccess, *, starred: bool) -> PrefsRead:
    """Star or unstar the board for me."""
    repo = BoardPrefsRepository(db, org_id=access.org_id)
    await repo.upsert(access.board.id, access.user_id, starred=starred)
    await db.commit()
    return await read_prefs(db, access)


async def set_filters(db: AsyncSession, access: BoardAccess, filters: BoardFilters) -> PrefsRead:
    """Save the filters to restore when I come back to the board."""
    repo = BoardPrefsRepository(db, org_id=access.org_id)
    await repo.upsert(access.board.id, access.user_id, filters=filters.model_dump(mode="json"))
    await db.commit()
    return await read_prefs(db, access)


def _entry(visible: VisibleBoard) -> SwitcherBoard:
    board = visible.board
    return SwitcherBoard(id=board.id, key=board.key, name=board.name, role=visible.role)


async def switcher(db: AsyncSession, caller: BoardCaller, q: str | None) -> SwitcherRead:
    """Starred, recent and other boards I can open, plus Delivery when I can see it."""
    q = q.strip() if q else None
    groups = await BoardSwitcherRepository(db, org_id=caller.org_id).groups(
        caller.user_id,
        caller.perms,
        q=q,
        recent_limit=settings.boards.switcher_recent_limit,
        other_limit=settings.boards.switcher_other_limit,
    )
    return SwitcherRead(
        starred=[_entry(v) for v in groups.starred],
        recent=[_entry(v) for v in groups.recent],
        other=[_entry(v) for v in groups.other],
        delivery=_delivery(caller, q),
    )


def _delivery(caller: BoardCaller, q: str | None) -> DeliveryBoardItem | None:
    item = delivery_item(caller)
    if item is None or (q and q.lower() not in item.name.lower()):
        return None
    return item
