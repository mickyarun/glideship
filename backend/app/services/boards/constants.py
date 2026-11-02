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

"""Fixed rules for boards: reserved keys, handover landings, and who may do what.

Tunables (sizes, intervals, limits) live in :class:`app.config.BoardsConfig`.
"""

import re
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from app.models.agent_skill import AgentType
from app.models.board_enums import BoardCardDocKind, BoardMemberRole, StageRequiredField
from app.models.bud import BUDStatus

BOARD_KEY_MIN_LENGTH: Final = 2
BOARD_KEY_MAX_LENGTH: Final = 10

# Card keys are ``{board key}-{number}``; BUD and BUG already name BUDs and
# bugs. The others are fixed path segments under ``/api/v1/boards``, now or
# planned, that a board key would otherwise share.
# The Delivery (BUD) board's key: a card goes there by handover, not a move.
DELIVERY_BOARD_KEY: Final = "BUD"

RESERVED_BOARD_KEYS: Final = frozenset(
    {
        DELIVERY_BOARD_KEY,
        "BUG",
        "CARDS",
        "IMPORTS",
        "LIMITS",
        "METRICS",
        "SKILLS",
        "SWITCHER",
        "TEMPLATES",
    }
)

BOARD_KEY_PATTERN: Final = re.compile(rf"^[A-Z]{{{BOARD_KEY_MIN_LENGTH},{BOARD_KEY_MAX_LENGTH}}}$")

# Product limits on what people type and attach. They shape the UI, so the
# frontend reads them from ``GET /api/v1/boards/limits`` instead of copying.
BOARD_DESCRIPTION_MAX_CHARS: Final = 5_000
CARD_DESCRIPTION_MAX_CHARS: Final = 50_000
CARD_DOC_MAX_CHARS: Final = 200_000
COMMENT_MAX_CHARS: Final = 10_000
CHECKLIST_TEXT_MAX_CHARS: Final = 2_000
SEARCH_MAX_CHARS: Final = 200
CHECKLIST_MAX_ITEMS: Final = 100
LINKS_MAX_PER_CARD: Final = 50
# Assignees, labels and the id lists sent to reorder stages.
ID_LIST_MAX_ITEMS: Final = 50
WIP_LIMIT_MAX: Final = 999

# How a refused move names each missing field: "needs an assignee and a PRD".
STAGE_REQUIRED_FIELD_LABELS: Final = MappingProxyType(
    {
        StageRequiredField.ASSIGNEE: "an assignee",
        StageRequiredField.DUE_DATE: "a due date",
        StageRequiredField.PRIORITY: "a priority",
        StageRequiredField.LABEL: "a label",
        StageRequiredField.DESCRIPTION: "a description",
        StageRequiredField.PRD: "a PRD",
    }
)

# Linked repositories: a repository's page is ``GITHUB_WEB_URL/<owner>/<name>``,
# built only from a full name of that shape.
GITHUB_WEB_URL: Final = "https://github.com"
GITHUB_FULL_NAME_PATTERN: Final = re.compile(r"[\w.-]+/[\w.-]+", re.ASCII)

# The BUD board, listed beside team boards for members of the engineering workspace.
DELIVERY_BOARD_NAME: Final = "Delivery"
DELIVERY_BOARD_PATH: Final = "/buds"

# A handed-over card lands as a BUD before development starts; send-back
# accepts BUDs still at one of these statuses.
_BUD_ORDER: Final = list(BUDStatus)
HANDOVER_LANDING_STATUSES: Final = tuple(_BUD_ORDER[: _BUD_ORDER.index(BUDStatus.DEVELOPMENT)])
# How a handover tags the BUD status changes it writes, so learning metrics
# can tell skipped stages from finished ones.
VIA_HANDOVER: Final = "handover"
# A send-back reason becomes a card comment after a short lead naming the
# BUD ("Sent back from BUD-012: "), so it leaves room for that lead.
HANDOVER_RETURN_LEAD_MAX_CHARS: Final = 100
HANDOVER_RETURN_REASON_MAX_CHARS: Final = COMMENT_MAX_CHARS - HANDOVER_RETURN_LEAD_MAX_CHARS

# Stage agents. Any skill in the org's library can run on a stage; these
# two are the suggested defaults the stage picker offers first.
BOARD_AGENT_TYPES: Final = (AgentType.BOARD_PRD, AgentType.BOARD_DESIGN)
# The document a skill of each type writes; any other type writes notes.
AGENT_OUTPUT_KINDS: Final = MappingProxyType(
    {
        AgentType.BOARD_PRD: BoardCardDocKind.PRD,
        AgentType.BOARD_DESIGN: BoardCardDocKind.DESIGN_BRIEF,
        AgentType.BUD: BoardCardDocKind.PRD,
        AgentType.DESIGN: BoardCardDocKind.DESIGN_BRIEF,
    }
)
DEFAULT_AGENT_OUTPUT_KIND: Final = BoardCardDocKind.NOTES
# A card run's token always covers these two, for its one card.
WRITE_CARD_DOC_TOOL: Final = "write_card_doc"
GET_CARD_CONTEXT_TOOL: Final = "get_card_context"
CARD_RUN_TOOLS: Final = frozenset({WRITE_CARD_DOC_TOOL, GET_CARD_CONTEXT_TOOL})


class BoardAction(StrEnum):
    """Things someone can do on a board; the API reports the ones they may."""

    VIEW = "view"
    COMMENT = "comment"
    CREATE_CARD = "create_card"
    EDIT_CARD = "edit_card"
    MOVE_CARD = "move_card"
    ARCHIVE_CARD = "archive_card"
    # Also needs ``workspace:engineering`` and ``buds:create`` (``buds:edit`` to link).
    HAND_OVER = "hand_over"
    REVIEW_DRAFT = "review_draft"
    RUN_AGENT = "run_agent"
    EDIT_SETTINGS = "edit_settings"
    MANAGE_STAGES = "manage_stages"
    MANAGE_MEMBERS = "manage_members"
    MANAGE_LABELS = "manage_labels"
    CONFIGURE_AGENTS = "configure_agents"
    MANAGE_REPOS = "manage_repos"
    IMPORT = "import"
    ARCHIVE_BOARD = "archive_board"
    REMOVE_ANY_ATTACHMENT = "remove_any_attachment"


_VIEWER_ACTIONS: Final = (BoardAction.VIEW, BoardAction.COMMENT)
_EDITOR_ACTIONS: Final = (
    BoardAction.CREATE_CARD,
    BoardAction.EDIT_CARD,
    BoardAction.MOVE_CARD,
    BoardAction.ARCHIVE_CARD,
    BoardAction.HAND_OVER,
    BoardAction.REVIEW_DRAFT,
    BoardAction.RUN_AGENT,
)
_ADMIN_ACTIONS: Final = (
    BoardAction.EDIT_SETTINGS,
    BoardAction.MANAGE_STAGES,
    BoardAction.MANAGE_MEMBERS,
    BoardAction.MANAGE_LABELS,
    BoardAction.CONFIGURE_AGENTS,
    BoardAction.MANAGE_REPOS,
    BoardAction.IMPORT,
    BoardAction.ARCHIVE_BOARD,
    BoardAction.REMOVE_ANY_ATTACHMENT,
)

BOARD_ACTION_MIN_ROLE: Final = MappingProxyType(
    {
        **dict.fromkeys(_VIEWER_ACTIONS, BoardMemberRole.VIEWER),
        **dict.fromkeys(_EDITOR_ACTIONS, BoardMemberRole.EDITOR),
        **dict.fromkeys(_ADMIN_ACTIONS, BoardMemberRole.ADMIN),
    }
)


# All an archived board allows: reading it, and an admin restoring it.
ARCHIVED_BOARD_ACTIONS: Final = frozenset({BoardAction.VIEW, BoardAction.ARCHIVE_BOARD})


def capabilities_for(role: BoardMemberRole) -> list[BoardAction]:
    """Every action ``role`` may take, in declaration order."""
    return [action for action in BoardAction if role.at_least(BOARD_ACTION_MIN_ROLE[action])]
