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


"""Board access for the board MCP tools, checked again on every call.

A board tool needs a personal MCP token: the caller's org permissions are
read fresh each call and their role comes from the one board access rule
(:mod:`app.services.boards.access`), so a board the caller can't see
answers "not found" exactly as the API does. A board error comes back as
a tool error carrying the HTTP status and ``code`` the API would send, and
the call's session is rolled back first so nothing half-done is kept.
"""

import functools
import uuid
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import Any

import structlog
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._board_errors import status_for
from app.core.permission_deps import member_permission_set
from app.mcp.auth import MCPAuthResult
from app.services.boards.access import (
    BoardAccess,
    BoardArchivedError,
    BoardCaller,
    BoardForbiddenError,
    CardAccess,
    resolve_board_access,
    resolve_card_by_key,
)
from app.services.boards.constants import BOARD_ACTION_MIN_ROLE, BoardAction
from app.services.boards.errors import BoardError
from app.services.boards.origin_summary import origin_card_summary

logger = structlog.get_logger(__name__)

NEEDS_PERSONAL_TOKEN = "Board tools need a personal MCP token (Settings → MCP tokens)."

BoardTool = Callable[[AsyncSession, BoardCaller, dict[str, Any]], Awaitable[dict[str, Any]]]
AuthHandler = Callable[[AsyncSession, MCPAuthResult, dict[str, Any]], Awaitable[dict[str, Any]]]


def tool_error(message: str, http_status: int, /, **extra: Any) -> dict[str, Any]:
    """A tool error the caller can branch on: ``status`` mirrors the API's, ``extra``
    carries the API's ``code`` and facts when it sends them."""
    return {"success": False, "error": message, "status": int(http_status), **extra}


def missing(name: str) -> dict[str, Any]:
    """The tool error for a required parameter left out."""
    return tool_error(f"`{name}` is required", HTTPStatus.UNPROCESSABLE_ENTITY)


async def tool_caller(db: AsyncSession, auth: MCPAuthResult) -> BoardCaller | None:
    """The token's person with their current org permissions; None for other tokens."""
    if auth.user_id is None or auth.grant is not None:
        return None
    perms = await member_permission_set(db, auth.user_id, auth.org_id)
    if perms is None:
        return None
    return BoardCaller(user_id=auth.user_id, org_id=auth.org_id, perms=perms)


def board_tool(tool: BoardTool) -> AuthHandler:
    """Wrap a board tool: resolve the caller, and turn board and input errors into results."""

    @functools.wraps(tool)
    async def handler(
        db: AsyncSession, auth: MCPAuthResult, params: dict[str, Any]
    ) -> dict[str, Any]:
        caller = await tool_caller(db, auth)
        if caller is None:
            return tool_error(NEEDS_PERSONAL_TOKEN, HTTPStatus.FORBIDDEN)
        try:
            return await tool(db, caller, params)
        except BoardError as exc:
            await db.rollback()
            code = status_for(exc)
            logger.info("mcp_board_tool_refused", tool=tool.__name__, status=code)
            return tool_error(str(exc), code, **dict(exc.body()))
        except ValidationError as exc:
            await db.rollback()
            return tool_error(_validation_message(exc), HTTPStatus.UNPROCESSABLE_ENTITY)

    return handler


def _validation_message(exc: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(p) for p in err['loc']) or 'input'}: {err['msg']}" for err in exc.errors()
    )


def stripped(value: Any) -> str:
    """A string parameter's value, stripped; empty when it is missing or not a string.

    Handlers read each parameter as a literal ``params.get("name")`` and pass
    the value here, so the startup contract check (:mod:`app.mcp.contract_check`)
    sees every key they read.
    """
    return value.strip() if isinstance(value, str) else ""


async def board_for(
    db: AsyncSession, caller: BoardCaller, key: str, action: BoardAction
) -> BoardAccess:
    """The board keyed ``key``, if the caller may take ``action`` on it."""
    return await resolve_board_access(
        db,
        user_id=caller.user_id,
        org_id=caller.org_id,
        perms=caller.perms,
        key=key,
        min_role=BOARD_ACTION_MIN_ROLE[action],
        writable=action is not BoardAction.VIEW,
    )


async def card_for(
    db: AsyncSession, caller: BoardCaller, key: str, action: BoardAction
) -> CardAccess:
    """The card a live or old key names, if the caller may take ``action`` on its board."""
    target = await resolve_card_by_key(
        db, user_id=caller.user_id, org_id=caller.org_id, perms=caller.perms, key=key
    )
    access = target.access
    if not access.role.at_least(BOARD_ACTION_MIN_ROLE[action]):
        raise BoardForbiddenError()
    if not access.may(action):
        raise BoardArchivedError()
    return target


async def origin_card(
    db: AsyncSession, auth: MCPAuthResult, bud_id: uuid.UUID
) -> dict[str, Any] | None:
    """The BUD's origin card in brief, when the token's person can open its board."""
    caller = await tool_caller(db, auth)
    return None if caller is None else await origin_card_summary(db, caller, bud_id)
