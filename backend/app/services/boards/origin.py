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

"""A BUD's Origin panel: the card it came from, that card's comments and handovers.

The card is the BUD's live origin, else the card it was most recently
handed over from. Its comments and handovers are shown only to a caller
who can open the card's board now; anyone else learns only that it's
hidden, never the board's name or key.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.repositories.board import BoardRepository
from app.repositories.board_access import BoardAccessRepository
from app.repositories.board_card import BoardCardRepository
from app.repositories.board_card_thread import BoardCardCommentRepository
from app.repositories.board_handover import BoardHandoverRepository
from app.repositories.bud import BUDRepository
from app.schemas.boards.card_detail import CommentPage
from app.schemas.boards.handover_return import BUDOrigin, OriginBoard, OriginCard
from app.services.boards.access import BoardCaller
from app.services.boards.comment_service import read_comments
from app.services.boards.cursor import decode_time_cursor, encode_cursor
from app.services.boards.errors import BoardItemNotFoundError
from app.services.boards.handover_chips import opens_buds
from app.services.boards.handover_reads import handover_read
from app.services.boards.reads import card_key

BUD_NOT_FOUND = "BUD not found."


async def bud_origin(
    db: AsyncSession,
    caller: BoardCaller,
    bud_id: uuid.UUID,
    *,
    cursor: str | None,
    limit: int | None,
) -> BUDOrigin:
    """The BUD's origin card as the caller may see it.

    Raises:
        BoardItemNotFoundError: No such BUD in the caller's org.
    """
    org_id = caller.org_id
    if await BUDRepository(db, org_id=org_id).get_by_id(bud_id) is None:
        raise BoardItemNotFoundError(BUD_NOT_FOUND)
    handovers = BoardHandoverRepository(db, org_id=org_id)
    row = await handovers.latest_for_bud(bud_id)
    card = await BoardCardRepository(db, org_id=org_id).get_by_id(row.card_id) if row else None
    if card is None:
        return BUDOrigin(card=None)
    access = BoardAccessRepository(db, org_id=org_id)
    board = await BoardRepository(db, org_id=org_id).get_by_id(card.board_id)
    role = await access.role_for(card.board_id, caller.user_id, caller.perms)
    if board is None or role is None:
        return BUDOrigin(card=None, hidden=True)
    return BUDOrigin(
        card=OriginCard(
            key=card_key(board.key, card.number),
            number=card.number,
            title=card.title,
            board=OriginBoard(key=board.key, name=board.name),
        ),
        comments=await _comments(db, org_id, card.id, cursor=cursor, limit=limit),
        handovers=[
            handover_read(r, can_open_bud=opens_buds(caller.perms))
            for r in await handovers.list_for_card(card.id)
        ],
    )


async def _comments(
    db: AsyncSession,
    org_id: uuid.UUID,
    card_id: uuid.UUID,
    *,
    cursor: str | None,
    limit: int | None,
) -> CommentPage:
    """A page of the card's comments, newest first, tombstones in place."""
    size = limit or settings.boards.comments_page_size
    before = decode_time_cursor(cursor) if cursor else None
    repo = BoardCardCommentRepository(db, org_id=org_id)
    rows = await repo.newest_page(card_id, before=before, limit=size + 1)
    page = rows[:size]
    last = page[-1] if page and len(rows) > size else None
    return CommentPage(
        items=await read_comments(db, org_id, page),
        next_cursor=None
        if last is None
        else encode_cursor(last.created_at.isoformat(), str(last.id)),
    )
