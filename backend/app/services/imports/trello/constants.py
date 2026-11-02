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

"""Fixed facts about Trello: its API, its export, and how its names map to ours.

Tunables (rate, timeouts, retries, caps) live in :class:`app.config.BoardsConfig`.
"""

import re
from types import MappingProxyType
from typing import Final

from app.models.board_enums import BoardLabelColor, BoardStageCategory

# The only host the importer ever calls, for data and for attachment files.
TRELLO_API_HOST: Final = "api.trello.com"
TRELLO_API_BASE: Final = f"https://{TRELLO_API_HOST}"

# Trello's rate limits are counted over 10-second windows.
TRELLO_WINDOW_SECONDS: Final = 10.0

# Object ids are 24 hex characters; card short links are a few letters and digits.
TRELLO_ID_PATTERN: Final = re.compile(r"^[0-9a-fA-F]{24}$")
TRELLO_SHORT_LINK_PATTERN: Final = re.compile(r"^[0-9A-Za-z]{1,24}$")

# A board export holds only the newest 1,000 actions, and comments are
# actions, so an export at the cap has lost older comments.
TRELLO_EXPORT_ACTION_CAP: Final = 1000
# The most actions one API page returns; pages are walked with ``before``.
TRELLO_ACTIONS_PAGE_LIMIT: Final = 1000
TRELLO_COMMENT_ACTION: Final = "commentCard"
TRELLO_CHECK_ITEM_DONE: Final = "complete"

# The nested board read: everything the import maps, in one call.
TRELLO_BOARD_PARAMS: Final = MappingProxyType(
    {
        "fields": "name,url,shortLink,closed",
        "lists": "all",
        "cards": "all",
        "card_attachments": "true",
        "card_customFieldItems": "true",
        "labels": "all",
        "members": "all",
        "member_fields": "fullName,username",
        "checklists": "all",
        "customFields": "true",
    }
)
TRELLO_BOARDS_PARAMS: Final = MappingProxyType({"filter": "open", "fields": "name,url"})

# Imported comments by someone with no mapped user keep a name like this;
# the name is cut so the whole label fits its column.
AUTHOR_LABEL_FORMAT: Final = "{name} (Trello)"
UNKNOWN_AUTHOR: Final = "Someone"
UNTITLED_CARD: Final = "Untitled card"
SNAPSHOT_FILENAME: Final = "trello-board.json"

# List-name hints for a stage's category, checked in this order. A list
# with no hint is ``todo``, except the last open list, which is ``done``.
TRELLO_CATEGORY_HINTS: Final = (
    (BoardStageCategory.CANCELED, ("won't", "wont", "cancel", "rejected", "dropped")),
    (
        BoardStageCategory.DONE,
        ("done", "complete", "shipped", "published", "released", "live", "closed"),
    ),
    (
        BoardStageCategory.IN_PROGRESS,
        ("doing", "progress", "review", "writing", "wip", "testing", "active"),
    ),
)

# Trello colours are ours plus ``_dark`` / ``_light`` shades; no colour maps here.
TRELLO_COLOR_SHADES: Final = ("_dark", "_light")
TRELLO_DEFAULT_LABEL_COLOR: Final = BoardLabelColor.SKY
