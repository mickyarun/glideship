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


"""MCP tools that read and write a card's documents: ``get_card_context`` and ``write_card_doc``.

Inside a board agent run the token's grant names one card and one run
(:mod:`app.services.boards.agents.card_tools`); ``write_card_doc`` then
saves a ``pending_review`` draft that a person accepts, and anything
outside the grant is 403. With a personal token, ``write_card_doc`` saves a
new current version exactly as the card page does, for an editor of the
card's board, and like the card page it needs ``base_version`` (the current
version it started from) once the document exists. Neither tool is remote.
"""

from typing import Any

import structlog
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp.auth import MCPAuthResult
from app.mcp.board_tool_access import board_tool, card_for, missing, stripped
from app.models.board_enums import BoardCardDocKind
from app.schemas.boards.doc import DocWrite
from app.services.boards import doc_service
from app.services.boards.access import BoardCaller
from app.services.boards.agents.card_tools import (
    CardGrantError,
    GrantedCard,
    granted_card,
    read_card,
    write_card_draft,
)
from app.services.boards.constants import (
    CARD_DOC_MAX_CHARS,
    GET_CARD_CONTEXT_TOOL,
    WRITE_CARD_DOC_TOOL,
    BoardAction,
)
from app.services.boards.reads import card_key

logger = structlog.get_logger(__name__)


async def _granted(
    db: AsyncSession, auth: MCPAuthResult, card_id: Any, card_key_value: Any
) -> GrantedCard:
    try:
        return await granted_card(
            db,
            auth.grant,
            card_id=card_id if isinstance(card_id, str) else None,
            card_key_value=card_key_value if isinstance(card_key_value, str) else None,
        )
    except CardGrantError as exc:
        logger.warning("mcp_card_tool_refused", org_id=str(auth.org_id), reason=str(exc))
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


def _doc_input(kind_value: Any, content: Any) -> tuple[BoardCardDocKind, str] | dict[str, Any]:
    """The document kind and text, or the error to return."""
    kinds = [k.value for k in BoardCardDocKind]
    try:
        kind = BoardCardDocKind(str(kind_value))
    except ValueError:
        return {"success": False, "error": f"kind must be one of {kinds}"}
    if not isinstance(content, str) or not content.strip():
        return {"success": False, "error": "content_md must be a non-empty string"}
    if len(content) > CARD_DOC_MAX_CHARS:
        return {"success": False, "error": f"content_md is over {CARD_DOC_MAX_CHARS} characters"}
    return kind, content


async def handle_get_card_context(
    db: AsyncSession, auth: MCPAuthResult, params: dict[str, Any]
) -> dict[str, Any]:
    """The run's card and what surrounds it."""
    granted = await _granted(db, auth, params.get("card_id"), params.get("card_key"))
    return await read_card(db, granted)


async def handle_write_card_doc(
    db: AsyncSession, auth: MCPAuthResult, params: dict[str, Any]
) -> dict[str, Any]:
    """A current version for a person's token; a ``pending_review`` draft for an agent run's."""
    kind_value, content = params.get("kind"), params.get("content_md")
    if auth.grant is None and auth.user_id is not None:
        return await _write_as_person(db, auth, params)
    granted = await _granted(db, auth, params.get("card_id"), params.get("card_key"))
    parsed = _doc_input(kind_value, content)
    if isinstance(parsed, dict):
        return parsed
    kind, text = parsed
    result = await write_card_draft(db, granted, kind, text)
    logger.info(
        "mcp_write_card_doc",
        org_id=str(auth.org_id),
        card_id=str(granted.card.id),
        run_id=str(granted.run.id),
        kind=kind.value,
        length=len(text),
    )
    return result


@board_tool
async def _write_as_person(
    db: AsyncSession, caller: BoardCaller, params: dict[str, Any]
) -> dict[str, Any]:
    key = stripped(params.get("card_key"))
    if not key:
        return missing("card_key")
    parsed = _doc_input(params.get("kind"), params.get("content_md"))
    if isinstance(parsed, dict):
        return parsed
    kind, content = parsed
    target = await card_for(db, caller, key, BoardAction.EDIT_CARD)
    # As on the card page: once the document exists, base_version must name
    # its current version (omitted is "new document", so it's 409 then).
    body = DocWrite.model_validate(
        {"body_md": content, "base_version": params.get("base_version")}
    )
    doc = await doc_service.write_doc(
        db, target, kind, body.body_md, base_version=body.base_version
    )
    logger.info(
        "mcp_write_card_doc_current",
        org_id=str(caller.org_id),
        card_id=str(target.card.id),
        kind=kind.value,
        version=doc.version,
    )
    return {
        "saved": True,
        "card_key": card_key(target.access.board.key, target.card.number),
        "kind": kind.value,
        "version": doc.version,
        "state": doc.state.value,
    }


CARD_DOC_TOOL_HANDLERS: dict[str, Any] = {
    GET_CARD_CONTEXT_TOOL: handle_get_card_context,
    WRITE_CARD_DOC_TOOL: handle_write_card_doc,
}
