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
from app.repositories.board_prefs import BoardPrefsRepository
from app.repositories.board_stage import BoardStageRepository
from app.schemas.boards.board import (
    BoardCreate,
    BoardDetail,
    BoardList,
    BoardListItem,
    CardCounts,
    CustomBoardItem,
    DeliveryBoardItem,
    TemplateRead,
)
from app.services.boards.access import BoardAccess, BoardCaller
from app.services.boards.board_create import insert_board
from app.services.boards.board_template import BoardTemplate, load_templates
from app.services.boards.constants import DELIVERY_BOARD_NAME, DELIVERY_BOARD_PATH
from app.services.boards.errors import BoardRuleError
from app.services.boards.reads import board_detail


def delivery_item(caller: BoardCaller) -> DeliveryBoardItem | None:
    """The Delivery board entry, for callers who can open the engineering workspace."""
    if not caller.has_engineering:
        return None
    return DeliveryBoardItem(name=DELIVERY_BOARD_NAME, path=DELIVERY_BOARD_PATH)


def custom_item(visible: VisibleBoard) -> CustomBoardItem:
    """A team board as the list and the switcher show it."""
    board = visible.board
    counts = visible.counts
    return CustomBoardItem(
        id=board.id,
        key=board.key,
        name=board.name,
        description=board.description,
        visibility=board.visibility,
        handover_enabled=board.handover_enabled,
        role=visible.role,
        starred=visible.starred,
        last_opened_at=visible.last_opened_at,
        counts=CardCounts(
            todo=counts.todo, in_progress=counts.in_progress, done_recent=counts.done_recent
        ),
    )


async def list_boards(db: AsyncSession, caller: BoardCaller) -> BoardList:
    """Every board the caller can open, then Delivery when they may see it."""
    since = datetime.now(UTC) - timedelta(days=settings.boards.recent_done_days)
    visible = await BoardRepository(db, org_id=caller.org_id).list_visible(
        caller.user_id, caller.perms, done_since=since
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


async def create_board(db: AsyncSession, caller: BoardCaller, body: BoardCreate) -> BoardDetail:
    """A new board from a template, with the caller as its admin."""
    template = load_templates().get(body.template)
    if template is None:
        raise BoardRuleError(f"There is no board template called {body.template!r}.")
    board = await insert_board(
        db,
        caller,
        key=body.key,
        name=body.name,
        description=body.description,
        visibility=body.visibility,
    )
    await _add_template_stages(db, board, template)
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
