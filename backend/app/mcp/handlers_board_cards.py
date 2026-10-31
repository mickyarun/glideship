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


"""MCP tools for working on board cards from Claude Code with a personal token.

``get_card``, ``create_card``, ``update_card``, ``move_card`` and
``comment_card`` go through the same services as the board API, so stage
entry rules, label and repository checks and live events all apply. Each
call checks the caller's role on the card's board again
(:mod:`app.mcp.board_tool_access`). Old card keys resolve to the card's
current board.
"""

import uuid
from typing import Any, Final

from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp.board_tool_access import (
    board_for,
    board_tool,
    card_for,
    missing,
    stripped,
)
from app.mcp.board_tool_schemas import (
    COMMENT_CARD_TOOL,
    CREATE_CARD_TOOL,
    GET_CARD_TOOL,
    MOVE_CARD_TOOL,
    UPDATE_CARD_TOOL,
)
from app.repositories.board_stage import BoardStageRepository
from app.schemas.boards.card import CardCreate, CardDetail, CardMove, CardUpdate
from app.schemas.boards.card_detail import CommentBody
from app.services.boards import card_edit, card_move, card_service, comment_service
from app.services.boards.access import BoardAccess, BoardCaller
from app.services.boards.agents.context import card_context
from app.services.boards.constants import BoardAction
from app.services.boards.errors import BoardItemNotFoundError
from app.services.boards.handover_chips import opens_buds
from app.services.boards.reads import card_detail

STAGE_NOT_FOUND: Final = "Stage not found."
_EDIT_FIELDS: Final = (
    "title",
    "description_md",
    "priority",
    "start_at",
    "due_at",
    "assignee_ids",
    "label_ids",
    "repo_id",
)
_CARD_OUT: Final = {
    "id",
    "key",
    "board_key",
    "number",
    "stage_id",
    "title",
    "priority",
    "start_at",
    "due_at",
    "due_done",
    "assignee_ids",
    "label_ids",
    "repo_id",
    "archived_at",
}


def _picked(params: dict[str, Any], names: tuple[str, ...]) -> dict[str, Any]:
    return {name: params[name] for name in names if name in params}


def _card(detail: CardDetail) -> dict[str, Any]:
    return {"success": True, "card": detail.model_dump(mode="json", include=_CARD_OUT)}


async def _stage_id(db: AsyncSession, access: BoardAccess, ref: str) -> uuid.UUID:
    """The board's stage named ``ref`` (ignoring case) or with that id."""
    stages = await BoardStageRepository(db, org_id=access.org_id).list_for_board(access.board.id)
    wanted = ref.casefold()
    for stage in stages:
        if str(stage.id) == ref or stage.name.casefold() == wanted:
            return stage.id
    raise BoardItemNotFoundError(STAGE_NOT_FOUND)


@board_tool
async def handle_get_card(
    db: AsyncSession, caller: BoardCaller, params: dict[str, Any]
) -> dict[str, Any]:
    """The card a live or old key names, with what its page shows."""
    key = stripped(params.get("card_key"))
    if not key:
        return missing("card_key")
    target = await card_for(db, caller, key, BoardAction.VIEW)
    board, card = target.access.board, target.card
    detail = await card_detail(db, board, card, opens_buds=opens_buds(caller.perms))
    context = await card_context(db, board, card)
    handovers = [
        {
            "bud_key": chip.bud_key,
            "bud_status": chip.status.value,
            "handover_status": chip.handover_status.value,
        }
        for chip in detail.handovers
    ]
    summary = {
        **context["card"],
        "stage_id": str(detail.stage_id),
        "start_at": detail.start_at.isoformat() if detail.start_at else None,
        "archived": detail.archived_at is not None,
        "delivery": detail.delivery.value,
        "handovers": handovers,
    }
    return {**context, "card": summary}


@board_tool
async def handle_create_card(
    db: AsyncSession, caller: BoardCaller, params: dict[str, Any]
) -> dict[str, Any]:
    """A new card at the bottom of the named or default stage."""
    key = stripped(params.get("board_key"))
    if not key:
        return missing("board_key")
    access = await board_for(db, caller, key, BoardAction.CREATE_CARD)
    fields = _picked(params, (*_EDIT_FIELDS, "confirm_open_checklist"))
    fields["title"] = params.get("title")
    stage = stripped(params.get("stage"))
    if stage:
        fields["stage_id"] = await _stage_id(db, access, stage)
    return _card(await card_service.create_card(db, access, CardCreate.model_validate(fields)))


@board_tool
async def handle_update_card(
    db: AsyncSession, caller: BoardCaller, params: dict[str, Any]
) -> dict[str, Any]:
    """Edit the fields named; the rest stay."""
    key = stripped(params.get("card_key"))
    if not key:
        return missing("card_key")
    target = await card_for(db, caller, key, BoardAction.EDIT_CARD)
    body = CardUpdate.model_validate(_picked(params, (*_EDIT_FIELDS, "due_done")))
    return _card(await card_edit.update_card(db, target, body))


@board_tool
async def handle_move_card(
    db: AsyncSession, caller: BoardCaller, params: dict[str, Any]
) -> dict[str, Any]:
    """Move the card to the bottom of a stage on its board."""
    key, stage = stripped(params.get("card_key")), stripped(params.get("stage"))
    if not key or not stage:
        return missing("card_key" if not key else "stage")
    target = await card_for(db, caller, key, BoardAction.MOVE_CARD)
    body = CardMove.model_validate(
        {
            "stage_id": await _stage_id(db, target.access, stage),
            **_picked(params, ("confirm_open_checklist",)),
        }
    )
    return _card(await card_move.move_card(db, target, body))


@board_tool
async def handle_comment_card(
    db: AsyncSession, caller: BoardCaller, params: dict[str, Any]
) -> dict[str, Any]:
    """Post a comment on the card."""
    key = stripped(params.get("card_key"))
    if not key:
        return missing("card_key")
    target = await card_for(db, caller, key, BoardAction.COMMENT)
    body = CommentBody.model_validate({"body": params.get("body")})
    comment = await comment_service.add_comment(db, target, body.body)
    return {"success": True, "comment": comment.model_dump(mode="json")}


BOARD_CARD_TOOL_HANDLERS: dict[str, Any] = {
    GET_CARD_TOOL: handle_get_card,
    CREATE_CARD_TOOL: handle_create_card,
    UPDATE_CARD_TOOL: handle_update_card,
    MOVE_CARD_TOOL: handle_move_card,
    COMMENT_CARD_TOOL: handle_comment_card,
}
