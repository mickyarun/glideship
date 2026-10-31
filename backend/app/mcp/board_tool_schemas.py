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


"""Input schemas of the board MCP tools, and which of them are remote.

``write_card_doc`` and ``get_card_context`` also serve board agent runs,
whose scoped token names one card (:mod:`app.mcp.handlers_board_docs`).
"""

from typing import Any, Final

from app.models.board_enums import BoardCardDocKind
from app.models.bud import BUDPriority
from app.services.boards.constants import GET_CARD_CONTEXT_TOOL, WRITE_CARD_DOC_TOOL

LIST_BOARDS_TOOL: Final = "list_boards"
GET_BOARD_TOOL: Final = "get_board"
GET_CARD_TOOL: Final = "get_card"
CREATE_CARD_TOOL: Final = "create_card"
UPDATE_CARD_TOOL: Final = "update_card"
MOVE_CARD_TOOL: Final = "move_card"
COMMENT_CARD_TOOL: Final = "comment_card"
# Read-only, so also served by the remote ``/mcp/sse`` endpoint.
REMOTE_BOARD_TOOLS: Final = frozenset({LIST_BOARDS_TOOL, GET_BOARD_TOOL, GET_CARD_TOOL})

_STR: Final[dict[str, Any]] = {"type": "string"}
_IDS: Final[dict[str, Any]] = {"type": "array", "items": {"type": "string"}}
_BOARD_KEY: Final = {"type": "string", "description": "The board's key, e.g. SEO."}
_CARD_KEY: Final = {
    "type": "string",
    "description": "The card's key, e.g. SEO-14 (old keys work).",
}
_STAGE: Final = {"type": "string", "description": "A stage of the board, by name or id."}
_WHEN: Final = {"type": "string", "description": "ISO 8601 with a timezone; null clears it."}
_CONFIRM: Final = {
    "type": "boolean",
    "description": "Enter a done stage although checklist items are open.",
}
_FIELDS: Final[dict[str, Any]] = {
    "title": _STR,
    "description_md": _STR,
    "priority": {"type": "string", "enum": [p.value for p in BUDPriority]},
    "start_at": _WHEN,
    "due_at": _WHEN,
    "assignee_ids": _IDS,
    "label_ids": _IDS,
    "repo_id": {"type": "string", "description": "One of the board's linked repositories."},
}
_REFUSALS: Final = (
    " A refusal returns success false with the API's status (404 when you can't see the "
    "board, 403 below the role, 409 archived) and, for stage rules, its code "
    "(STAGE_REQUIREMENTS_MISSING, CHECKLIST_OPEN)."
)


def _tool(name: str, description: str, props: dict[str, Any], *required: str) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "object", "properties": props}
    if required:
        schema["required"] = list(required)
    return {"name": name, "description": description, "input_schema": schema}


BOARD_TOOL_DEFINITIONS: Final[list[dict[str, Any]]] = [
    _tool(LIST_BOARDS_TOOL, "List the boards I can open, with my role and card counts.", {}),
    _tool(
        GET_BOARD_TOOL,
        "Read a board: its stages in order, each with its open cards, and its labels.",
        {"board_key": _BOARD_KEY},
        "board_key",
    ),
    _tool(
        GET_CARD_TOOL,
        "Read a card by key: its fields, stage, documents, newest comments, checklist, "
        "attachments, linked repositories and handover status.",
        {"card_key": _CARD_KEY},
        "card_key",
    ),
    _tool(
        CREATE_CARD_TOOL,
        "Create a card at the bottom of a stage (the board's default stage when none is "
        "named). The stage's entry rules apply." + _REFUSALS,
        {"board_key": _BOARD_KEY, "stage": _STAGE, **_FIELDS, "confirm_open_checklist": _CONFIRM},
        "board_key",
        "title",
    ),
    _tool(
        UPDATE_CARD_TOOL,
        "Edit a card's title, description, priority, start and due dates, assignees, labels "
        "or repository. Omitted fields stay; null clears one." + _REFUSALS,
        {"card_key": _CARD_KEY, **_FIELDS, "due_done": {"type": "boolean"}},
        "card_key",
    ),
    _tool(
        MOVE_CARD_TOOL,
        "Move a card to the bottom of another stage of its board. The stage's entry rules "
        "apply." + _REFUSALS,
        {"card_key": _CARD_KEY, "stage": _STAGE, "confirm_open_checklist": _CONFIRM},
        "card_key",
        "stage",
    ),
    _tool(
        COMMENT_CARD_TOOL,
        "Add a comment to a card." + _REFUSALS,
        {"card_key": _CARD_KEY, "body": _STR},
        "card_key",
        "body",
    ),
    _tool(
        GET_CARD_CONTEXT_TOOL,
        "Inside a board agent run: read the run's card, its documents, newest comments, "
        "checklist, attachment names and the board's linked repos.",
        {"card_id": {"type": "string", "description": "The card's id."}, "card_key": _CARD_KEY},
    ),
    _tool(
        WRITE_CARD_DOC_TOOL,
        "Write a card's PRD, design brief or notes. With a personal token this saves a new "
        "current version, as the card page does (base_version: the version you started "
        "from, null for a new document; omit it to write over the current one). Inside a "
        "board agent run it saves a draft that waits for review." + _REFUSALS,
        {
            "card_id": {"type": "string", "description": "Agent runs: the card's id."},
            "card_key": _CARD_KEY,
            "kind": {"type": "string", "enum": [k.value for k in BoardCardDocKind]},
            "content_md": {"type": "string", "description": "The document, in Markdown."},
            "base_version": {
                "type": "integer",
                "description": "Personal tokens: the version you edited from (null: new).",
            },
        },
        "kind",
        "content_md",
    ),
]


def remote_board_tool_schemas() -> list[dict[str, Any]]:
    """The read-only board tools as the remote endpoint lists them."""
    return [
        {"name": t["name"], "description": t["description"], "inputSchema": t["input_schema"]}
        for t in BOARD_TOOL_DEFINITIONS
        if t["name"] in REMOTE_BOARD_TOOLS
    ]
