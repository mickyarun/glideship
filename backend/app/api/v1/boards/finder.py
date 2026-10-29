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

"""Routes that don't name a board: templates, the switcher and card keys.

Mounted before the ``/{key}`` routes, so these paths are never read as a
board key (the words are reserved keys too).
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.board_deps import board_caller
from app.core.deps import get_db
from app.schemas.boards.board import TemplateRead
from app.schemas.boards.card import CardDetail
from app.schemas.boards.prefs import SwitcherRead
from app.schemas.boards.text import SEARCH_MAX_LENGTH
from app.services.boards import board_service, prefs_service
from app.services.boards.access import BoardCaller, resolve_card_by_key
from app.services.boards.reads import card_detail

router = APIRouter(tags=["boards"])


@router.get("/templates", response_model=list[TemplateRead])
async def list_templates() -> list[TemplateRead]:
    """Templates a new board can start from."""
    return board_service.list_templates()


@router.get("/switcher", response_model=SwitcherRead)
async def switcher(
    q: str | None = Query(default=None, max_length=SEARCH_MAX_LENGTH),
    caller: BoardCaller = Depends(board_caller),
    db: AsyncSession = Depends(get_db),
) -> SwitcherRead:
    """Starred, recent and other boards I can open, searched on the server."""
    return await prefs_service.switcher(db, caller, q)


@router.get("/cards/by-key/{card_key}", response_model=CardDetail)
async def card_by_key(
    card_key: str,
    caller: BoardCaller = Depends(board_caller),
    db: AsyncSession = Depends(get_db),
) -> CardDetail:
    """A card by its key, e.g. ``SEO-14``, or a key it had on another board."""
    target = await resolve_card_by_key(
        db, user_id=caller.user_id, org_id=caller.org_id, perms=caller.perms, key=card_key
    )
    return await card_detail(db, target.access.board, target.card)
