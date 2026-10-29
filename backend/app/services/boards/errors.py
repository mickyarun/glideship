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

"""Errors board services raise; ``api/v1/_board_errors.py`` maps them to HTTP.

Each message is written for the person using the board and is sent as the
response ``detail``. Access errors (no role, too low a role, archived
board) live in :mod:`app.services.boards.access`.
"""


class BoardError(Exception):
    """Base class for board errors."""


class BoardItemNotFoundError(BoardError):
    """A card, stage, label, member or document isn't on this board."""


class BoardConflictError(BoardError):
    """The change clashes with the board's current state."""


class BoardRuleError(BoardError):
    """The change breaks one of the board's rules."""


class BoardTooLargeError(BoardError):
    """An upload is bigger than the board accepts."""


class BoardStorageError(BoardError):
    """File storage failed; the request can be retried."""


class BoardActionForbiddenError(BoardError):
    """The caller may use the board but not take this action."""


# One message for a taken key or name, whichever board holds it, so a
# members-only board's key or name can't be discovered by trying it.
BOARD_TAKEN = "That key or name is already used by another board."
