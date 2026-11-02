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

"""The board action each kind of route performs, named once for every module.

Each dependency resolves the caller's board role for one ``BoardAction``;
the role it needs comes from ``BOARD_ACTION_MIN_ROLE``. Every write refuses
an archived board with 409, except restoring it and personal prefs.
"""

from app.core.board_deps import require_action, require_card_action
from app.services.boards.constants import BoardAction

view_board = require_action(BoardAction.VIEW)
edit_settings = require_action(BoardAction.EDIT_SETTINGS)
archive_board = require_action(BoardAction.ARCHIVE_BOARD)
restore_board = require_action(BoardAction.ARCHIVE_BOARD, writable=False)
manage_stages = require_action(BoardAction.MANAGE_STAGES)
manage_members = require_action(BoardAction.MANAGE_MEMBERS)
manage_labels = require_action(BoardAction.MANAGE_LABELS)
manage_repos = require_action(BoardAction.MANAGE_REPOS)
create_card = require_action(BoardAction.CREATE_CARD)
configure_agents = require_action(BoardAction.CONFIGURE_AGENTS)
configure_agents_read = require_action(BoardAction.CONFIGURE_AGENTS, writable=False)

view_card = require_card_action(BoardAction.VIEW)
comment_card = require_card_action(BoardAction.COMMENT)
edit_card = require_card_action(BoardAction.EDIT_CARD)
move_card = require_card_action(BoardAction.MOVE_CARD)
archive_card = require_card_action(BoardAction.ARCHIVE_CARD)
hand_over_card = require_card_action(BoardAction.HAND_OVER)
run_agent = require_card_action(BoardAction.RUN_AGENT)
review_draft = require_card_action(BoardAction.REVIEW_DRAFT)
