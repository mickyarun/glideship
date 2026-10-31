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
response ``detail``. An error a client acts on also sends a ``code`` and
its facts next to it (:meth:`BoardError.body`). Access errors (no role,
too low a role, archived board) live in :mod:`app.services.boards.access`.
"""

from collections.abc import Mapping
from enum import StrEnum
from typing import Any

# One message for a taken key or name, whichever board holds it, so a
# members-only board's key or name can't be discovered by trying it.
BOARD_TAKEN = "That key or name is already used by another board."


class BoardErrorCode(StrEnum):
    """Every ``code`` a board or import error sends beside ``detail``; clients branch on these."""

    STAGE_REQUIREMENTS_MISSING = "STAGE_REQUIREMENTS_MISSING"
    CHECKLIST_OPEN = "CHECKLIST_OPEN"
    BOARD_KEY_TAKEN = "BOARD_KEY_TAKEN"
    STAGE_GONE = "STAGE_GONE"
    STAGE_NAME_TAKEN = "STAGE_NAME_TAKEN"
    TOO_MANY_OPEN_IMPORTS = "TOO_MANY_OPEN_IMPORTS"
    IMPORT_STILL_WORKING = "IMPORT_STILL_WORKING"
    HANDOVER_DISABLED = "HANDOVER_DISABLED"
    HANDOVER_NEEDS_PERMISSION = "HANDOVER_NEEDS_PERMISSION"
    HANDOVER_NEEDS_REQUIREMENTS = "HANDOVER_NEEDS_REQUIREMENTS"
    BUD_HAS_OTHER_ORIGIN = "BUD_HAS_OTHER_ORIGIN"
    BUD_ALREADY_LINKED = "BUD_ALREADY_LINKED"
    BUD_NOT_OPEN = "BUD_NOT_OPEN"
    HANDOVER_NOT_ACTIVE = "HANDOVER_NOT_ACTIVE"
    BUD_PAST_RETURN = "BUD_PAST_RETURN"
    BUD_NOT_RETURNED = "BUD_NOT_RETURNED"
    HANDOVER_STAGE_STARTED = "HANDOVER_STAGE_STARTED"
    AI_DISABLED = "AI_DISABLED"
    AGENT_RUN_ACTIVE = "AGENT_RUN_ACTIVE"
    SKILL_NOT_IN_LIBRARY = "SKILL_NOT_IN_LIBRARY"
    AGENT_RUN_LIMIT = "AGENT_RUN_LIMIT"


class BoardError(Exception):
    """Base class for board errors."""

    def body(self) -> Mapping[str, Any]:
        """Fields sent next to ``detail``; none unless a subclass names a code."""
        return {}


class BoardItemNotFoundError(BoardError):
    """A card, stage, label, member or document isn't on this board."""


class BoardConflictError(BoardError):
    """The change clashes with the board's current state."""


class BoardTakenError(BoardConflictError):
    """A new board's key or name is taken (409 ``BOARD_KEY_TAKEN``, shown on the key field)."""

    def __init__(self) -> None:
        super().__init__(BOARD_TAKEN)

    def body(self) -> Mapping[str, Any]:
        """The code and the form field the clash belongs to."""
        return {"code": BoardErrorCode.BOARD_KEY_TAKEN, "field": "key"}


class BoardRuleError(BoardError):
    """The change breaks one of the board's rules."""


class BoardTooLargeError(BoardError):
    """An upload is bigger than the board accepts."""


class BoardStorageError(BoardError):
    """File storage failed; the request can be retried."""


class BoardActionForbiddenError(BoardError):
    """The caller may use the board but not take this action."""


class BoardRetryLaterError(BoardError):
    """The request can't be served now; ``retry_after_seconds`` says when to try again."""

    def __init__(self, message: str, *, retry_after_seconds: int) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class BoardRateLimitedError(BoardRetryLaterError):
    """The caller has made too many of these requests lately."""


class BoardBusyError(BoardRetryLaterError):
    """The server is too busy (or shutting down) to take the work now."""
