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

from app.models.board_enums import BoardMemberRole
from app.models.bud import BUDStatus

BOARD_KEY_MIN_LENGTH: Final = 2
BOARD_KEY_MAX_LENGTH: Final = 10

# Card keys are ``{board key}-{number}``; these prefixes already name BUDs and bugs.
RESERVED_BOARD_KEYS: Final = frozenset({"BUD", "BUG"})

BOARD_KEY_PATTERN: Final = re.compile(rf"^[A-Z]{{{BOARD_KEY_MIN_LENGTH},{BOARD_KEY_MAX_LENGTH}}}$")

# A handed-over card lands as a BUD before development starts; send-back
# accepts BUDs still at one of these statuses.
_BUD_ORDER: Final = list(BUDStatus)
HANDOVER_LANDING_STATUSES: Final = tuple(_BUD_ORDER[: _BUD_ORDER.index(BUDStatus.DEVELOPMENT)])


class BoardAction(StrEnum):
    """Things someone can do on a board; the API reports the ones they may."""

    VIEW = "view"
    COMMENT = "comment"
    CREATE_CARD = "create_card"
    EDIT_CARD = "edit_card"
    MOVE_CARD = "move_card"
    ARCHIVE_CARD = "archive_card"
    REVIEW_DRAFT = "review_draft"
    RUN_AGENT = "run_agent"
    EDIT_SETTINGS = "edit_settings"
    MANAGE_STAGES = "manage_stages"
    MANAGE_MEMBERS = "manage_members"
    MANAGE_LABELS = "manage_labels"
    CONFIGURE_AGENTS = "configure_agents"
    IMPORT = "import"
    ARCHIVE_BOARD = "archive_board"


_VIEWER_ACTIONS: Final = (BoardAction.VIEW, BoardAction.COMMENT)
_EDITOR_ACTIONS: Final = (
    BoardAction.CREATE_CARD,
    BoardAction.EDIT_CARD,
    BoardAction.MOVE_CARD,
    BoardAction.ARCHIVE_CARD,
    BoardAction.REVIEW_DRAFT,
    BoardAction.RUN_AGENT,
)
_ADMIN_ACTIONS: Final = (
    BoardAction.EDIT_SETTINGS,
    BoardAction.MANAGE_STAGES,
    BoardAction.MANAGE_MEMBERS,
    BoardAction.MANAGE_LABELS,
    BoardAction.CONFIGURE_AGENTS,
    BoardAction.IMPORT,
    BoardAction.ARCHIVE_BOARD,
)

BOARD_ACTION_MIN_ROLE: Final = MappingProxyType(
    {
        **dict.fromkeys(_VIEWER_ACTIONS, BoardMemberRole.VIEWER),
        **dict.fromkeys(_EDITOR_ACTIONS, BoardMemberRole.EDITOR),
        **dict.fromkeys(_ADMIN_ACTIONS, BoardMemberRole.ADMIN),
    }
)


def capabilities_for(role: BoardMemberRole) -> list[BoardAction]:
    """Every action ``role`` may take, in declaration order."""
    return [action for action in BoardAction if role.at_least(BOARD_ACTION_MIN_ROLE[action])]
