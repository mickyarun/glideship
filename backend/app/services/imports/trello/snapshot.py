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


"""Fetching a whole board from the Trello API, within the snapshot caps.

The board and all its comment pages together stay under
``BoardsConfig.import_max_snapshot_bytes``, and the comments under
``import_max_actions``; past either the import is refused with a clear
message, and the bigger board can't be imported here.
"""

from typing import Any

from app.config import settings
from app.services.imports.trello.client import TrelloClient


async def fetch_snapshot(client: TrelloClient, board_ref: str) -> dict[str, Any]:
    """The nested board with every comment as its ``actions``."""
    cfg = settings.boards
    board, used = await client.board(board_ref, cfg.import_max_snapshot_bytes)
    room = cfg.import_max_snapshot_bytes - used
    board_id = board.get("id")
    board["actions"] = await client.comments(
        board_id if isinstance(board_id, str) else "", room, cfg.import_max_actions
    )
    return board
