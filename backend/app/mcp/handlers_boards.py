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


"""MCP tools for reading boards: ``list_boards`` and ``get_board``.

Both need a personal token and check the caller's board role on every call
(:mod:`app.mcp.board_tool_access`). Both are also remote tools.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.mcp.board_tool_access import board_for, board_tool, missing, text_param
from app.mcp.board_tool_schemas import GET_BOARD_TOOL, LIST_BOARDS_TOOL
from app.repositories.board_card_filters import CardQuery
from app.schemas.boards.card import CardSummary
from app.services.boards import board_service, card_service
from app.services.boards.access import BoardCaller
from app.services.boards.constants import BoardAction
from app.services.boards.reads import board_detail


def card_line(card: CardSummary) -> dict[str, Any]:
    """A card as a stage lists it."""
    return {
        "key": card.key,
        "title": card.title,
        "priority": card.priority.value if card.priority else None,
        "due_at": card.due_at.isoformat() if card.due_at else None,
        "assignee_ids": [str(u) for u in card.assignee_ids],
        "label_ids": [str(label) for label in card.label_ids],
        "checklist": f"{card.checklist_done}/{card.checklist_total}",
        "delivery": card.delivery.value,
    }


@board_tool
async def handle_list_boards(
    db: AsyncSession, caller: BoardCaller, params: dict[str, Any]
) -> dict[str, Any]:
    """The boards the caller can open."""
    listed = await board_service.list_boards(db, caller)
    return listed.model_dump(mode="json")


@board_tool
async def handle_get_board(
    db: AsyncSession, caller: BoardCaller, params: dict[str, Any]
) -> dict[str, Any]:
    """The board's stages, each with its open cards, and its labels."""
    key = text_param(params, "board_key")
    if not key:
        return missing("board_key")
    access = await board_for(db, caller, key, BoardAction.VIEW)
    detail = await board_detail(db, access)
    limit = settings.boards.mcp_cards_per_stage
    stages: list[dict[str, Any]] = []
    for stage in detail.stages:
        page = await card_service.list_cards(db, access, CardQuery(stage_id=stage.id, limit=limit))
        stages.append(
            {
                "id": str(stage.id),
                "name": stage.name,
                "category": stage.category.value,
                "wip_limit": stage.wip_limit,
                "open_cards": stage.open_cards,
                "cards": [card_line(card) for card in page.items],
                "more_cards": page.next_cursor is not None,
            }
        )
    board = detail.board
    return {
        "board": {
            "key": board.key,
            "name": board.name,
            "description": board.description,
            "status": board.status.value,
            "visibility": board.visibility.value,
        },
        "role": detail.role.value,
        "capabilities": [action.value for action in detail.capabilities],
        "stages": stages,
        "labels": [{"id": str(lb.id), "name": lb.name} for lb in detail.labels],
    }


BOARD_TOOL_HANDLERS: dict[str, Any] = {
    LIST_BOARDS_TOOL: handle_list_boards,
    GET_BOARD_TOOL: handle_get_board,
}
