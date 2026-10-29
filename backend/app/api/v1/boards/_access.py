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

"""The access each kind of board route needs, named once for every module.

Reads need any role; comments need any role on an active board; card work
needs an editor; settings, stages, members and labels need an admin. Every
write refuses an archived board with 409, except restoring it.
"""

from app.core.board_deps import require_board, require_card
from app.models.board_enums import BoardMemberRole

VIEWER, EDITOR, ADMIN = BoardMemberRole.VIEWER, BoardMemberRole.EDITOR, BoardMemberRole.ADMIN

read_board = require_board(VIEWER)
edit_board = require_board(EDITOR, writable=True)
admin_board = require_board(ADMIN, writable=True)
restore_board = require_board(ADMIN)

read_card = require_card(VIEWER)
comment_card = require_card(VIEWER, writable=True)
edit_card = require_card(EDITOR, writable=True)
