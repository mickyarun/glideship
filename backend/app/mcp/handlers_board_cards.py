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

"""MCP tools for a board card's agent run: ``get_card_context`` and ``write_card_doc``.

Only a run's own token can use them: its grant names one card and one run
(:mod:`app.services.boards.agents.card_tools`). Anything else is 403. The
draft written is always ``pending_review``; a person accepts it. Neither
tool is in ``REMOTE_TOOLS``.
"""

from typing import Any

import structlog
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp.auth import MCPAuthResult
from app.models.board_enums import BoardCardDocKind
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
)

logger = structlog.get_logger(__name__)

_CARD_REF_SCHEMA: dict[str, Any] = {
    "card_id": {"type": "string", "description": "The card's id (from the prompt)."},
    "card_key": {"type": "string", "description": "Or the card's key, e.g. SEO-14."},
}

CARD_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": GET_CARD_CONTEXT_TOOL,
        "description": (
            "Read the board card this run works on: its fields, current documents, "
            "newest comments, checklist, attachment names and the board's linked repos."
        ),
        "input_schema": {"type": "object", "properties": dict(_CARD_REF_SCHEMA)},
    },
    {
        "name": WRITE_CARD_DOC_TOOL,
        "description": (
            "Save a draft document on the board card this run works on. The draft "
            "waits for a person to review it; it never replaces the card's current "
            "document by itself. kind is prd, design_brief or notes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                **_CARD_REF_SCHEMA,
                "kind": {"type": "string", "enum": [k.value for k in BoardCardDocKind]},
                "content_md": {"type": "string", "description": "The document, in Markdown."},
            },
            "required": ["kind", "content_md"],
        },
    },
]


async def _granted(
    db: AsyncSession, auth: MCPAuthResult, card_id: Any, card_key: Any
) -> GrantedCard:
    try:
        return await granted_card(
            db,
            auth.grant,
            card_id=card_id if isinstance(card_id, str) else None,
            card_key_value=card_key if isinstance(card_key, str) else None,
        )
    except CardGrantError as exc:
        logger.warning("mcp_card_tool_refused", org_id=str(auth.org_id), reason=str(exc))
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


async def handle_get_card_context(
    db: AsyncSession, auth: MCPAuthResult, params: dict[str, Any]
) -> dict[str, Any]:
    """The run's card and what surrounds it."""
    granted = await _granted(db, auth, params.get("card_id"), params.get("card_key"))
    return await read_card(db, granted)


async def handle_write_card_doc(
    db: AsyncSession, auth: MCPAuthResult, params: dict[str, Any]
) -> dict[str, Any]:
    """Save a ``pending_review`` draft on the run's card."""
    granted = await _granted(db, auth, params.get("card_id"), params.get("card_key"))
    raw_kind = params.get("kind")
    content = params.get("content_md")
    try:
        kind = BoardCardDocKind(str(raw_kind))
    except ValueError:
        return {
            "success": False,
            "error": f"kind must be one of {[k.value for k in BoardCardDocKind]}",
        }
    if not isinstance(content, str) or not content.strip():
        return {"success": False, "error": "content_md must be a non-empty string"}
    if len(content) > CARD_DOC_MAX_CHARS:
        return {"success": False, "error": f"content_md is over {CARD_DOC_MAX_CHARS} characters"}
    result = await write_card_draft(db, granted, kind, content)
    logger.info(
        "mcp_write_card_doc",
        org_id=str(auth.org_id),
        card_id=str(granted.card.id),
        run_id=str(granted.run.id),
        kind=kind.value,
        length=len(content),
    )
    return result


CARD_TOOL_HANDLERS: dict[str, Any] = {
    GET_CARD_CONTEXT_TOOL: handle_get_card_context,
    WRITE_CARD_DOC_TOOL: handle_write_card_doc,
}
