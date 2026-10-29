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

"""Listing, creating and opening boards."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.board import Board, BoardStage
from app.models.board_enums import BoardMemberRole
from app.repositories.board import BoardRepository, VisibleBoard
from app.repositories.board_member import BoardMemberRepository
from app.repositories.board_prefs import BoardPrefsRepository
from app.repositories.board_stage import BoardStageRepository
from app.schemas.boards.board import (
    BoardCreate,
    BoardDetail,
    BoardList,
    BoardListItem,
    CustomBoardItem,
    DeliveryBoardItem,
    TemplateRead,
)
from app.services.boards.access import BoardAccess, BoardCaller
from app.services.boards.board_template import BoardTemplate, load_templates
from app.services.boards.constants import (
    BOARD_KEY_PATTERN,
    DELIVERY_BOARD_NAME,
    DELIVERY_BOARD_PATH,
    RESERVED_BOARD_KEYS,
)
from app.services.boards.errors import BOARD_TAKEN, BoardConflictError, BoardRuleError
from app.services.boards.reads import board_detail


def delivery_item(caller: BoardCaller) -> DeliveryBoardItem | None:
    """The Delivery board entry, for callers who can open the engineering workspace."""
    if not caller.has_engineering:
        return None
    return DeliveryBoardItem(name=DELIVERY_BOARD_NAME, path=DELIVERY_BOARD_PATH)


def custom_item(visible: VisibleBoard) -> CustomBoardItem:
    """A team board as the list and the switcher show it."""
    board = visible.board
    return CustomBoardItem(
        id=board.id,
        key=board.key,
        name=board.name,
        visibility=board.visibility,
        role=visible.role,
        starred=visible.starred,
    )


async def list_boards(db: AsyncSession, caller: BoardCaller) -> BoardList:
    """Every board the caller can open, then Delivery when they may see it."""
    visible = await BoardRepository(db, org_id=caller.org_id).list_visible(
        caller.user_id, caller.perms
    )
    items: list[BoardListItem] = [custom_item(v) for v in visible]
    delivery = delivery_item(caller)
    if delivery is not None:
        items.append(delivery)
    return BoardList(items=items)


def list_templates() -> list[TemplateRead]:
    """The templates a new board can start from."""
    return [
        TemplateRead(
            id=template_id,
            name=t.name,
            description=t.description,
            stages=list(t.stages),
            handover_stage=t.handover_stage,
            return_stage=t.return_stage,
        )
        for template_id, t in load_templates().items()
    ]


def normalise_key(raw: str) -> str:
    """An upper-case board key, or :class:`BoardRuleError` when it can't be one."""
    key = raw.strip().upper()
    if not BOARD_KEY_PATTERN.fullmatch(key):
        raise BoardRuleError("A board key is 2 to 10 letters, A to Z.")
    if key in RESERVED_BOARD_KEYS:
        raise BoardRuleError(f"{key} is reserved; pick another key.")
    return key


async def create_board(db: AsyncSession, caller: BoardCaller, body: BoardCreate) -> BoardDetail:
    """A new board from a template, with the caller as its admin."""
    key, name = normalise_key(body.key), body.name
    template = load_templates().get(body.template)
    if template is None:
        raise BoardRuleError(f"There is no board template called {body.template!r}.")
    repo = BoardRepository(db, org_id=caller.org_id)
    if await repo.key_or_name_taken(key=key, name=name):
        raise BoardConflictError(BOARD_TAKEN)
    board = Board(
        org_id=caller.org_id,
        name=name,
        key=key,
        description=body.description,
        visibility=body.visibility,
        created_by=caller.user_id,
    )
    if not await repo.insert(board):
        raise BoardConflictError(BOARD_TAKEN)
    await _add_template_stages(db, board, template)
    await BoardMemberRepository(db, org_id=caller.org_id).put_member(
        board.id, caller.user_id, BoardMemberRole.ADMIN
    )
    await db.commit()
    await db.refresh(board)
    access = BoardAccess(
        board=board,
        role=BoardMemberRole.ADMIN,
        user_id=caller.user_id,
        org_id=caller.org_id,
        perms=caller.perms,
    )
    return await board_detail(db, access)


async def _add_template_stages(db: AsyncSession, board: Board, template: BoardTemplate) -> None:
    stage_repo = BoardStageRepository(db, org_id=board.org_id)
    by_name: dict[str, BoardStage] = {}
    for position, spec in enumerate(template.stages):
        stage = BoardStage(
            org_id=board.org_id,
            board_id=board.id,
            name=spec.name,
            category=spec.category,
            position=position,
            wip_limit=spec.wip_limit,
            is_default=spec.default,
        )
        await stage_repo.add(stage)
        by_name[spec.name] = stage
    await stage_repo.flush()
    if template.handover_stage is not None:
        board.handover_stage_id = by_name[template.handover_stage].id
    if template.return_stage is not None:
        board.return_stage_id = by_name[template.return_stage].id
    await stage_repo.flush()


async def open_board(db: AsyncSession, access: BoardAccess) -> BoardDetail:
    """The board's page data, recording the visit for the switcher's recent list.

    Although this serves a GET, it may write: ``last_opened_at`` is updated
    at most once per ``prefs_touch_interval_seconds``, for viewers too and
    on archived boards, since it's the caller's own preference row.
    """
    interval = timedelta(seconds=settings.boards.prefs_touch_interval_seconds)
    prefs = BoardPrefsRepository(db, org_id=access.org_id)
    touched = await prefs.touch_opened(
        access.board.id, access.user_id, now=datetime.now(UTC), interval=interval
    )
    if touched:
        await db.commit()
    return await board_detail(db, access)
