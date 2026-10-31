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

"""Import errors, on the board error classes so the boards API maps them to HTTP.

A conflict the review screen reacts to on its own carries a
:class:`BoardErrorCode` (and its facts) beside ``detail``.
"""

from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from app.services.boards.errors import (
    BoardConflictError,
    BoardErrorCode,
    BoardItemNotFoundError,
    BoardRuleError,
    BoardStorageError,
)

IMPORT_NOT_FOUND = "Import not found."
STAGE_NAME_TAKEN = "The target board already has a stage called {name!r}; map the list to it."


class OpenImportScope(StrEnum):
    """Whose open imports reached the cap: the caller's own, or the whole organisation's."""

    USER = "user"
    ORG = "org"


class ImportNotFoundError(BoardItemNotFoundError):
    """No such import in the org, or the caller didn't start it."""

    def __init__(self) -> None:
        super().__init__(IMPORT_NOT_FOUND)


class ImportStateError(BoardConflictError):
    """The import isn't at a step where this can happen; ``code`` names the step when set."""

    def __init__(self, message: str, *, code: BoardErrorCode | None = None) -> None:
        super().__init__(message)
        self.code = code

    def body(self) -> Mapping[str, Any]:
        """The code, when this conflict has one."""
        return {} if self.code is None else {"code": self.code}


class TooManyOpenImportsError(ImportStateError):
    """An open-imports cap is reached (409 ``TOO_MANY_OPEN_IMPORTS``, with its ``scope``)."""

    def __init__(self, message: str, *, scope: OpenImportScope) -> None:
        super().__init__(message, code=BoardErrorCode.TOO_MANY_OPEN_IMPORTS)
        self.scope = scope

    def body(self) -> Mapping[str, Any]:
        """The code and whose cap it is."""
        return {**super().body(), "scope": self.scope}


class StageNameTakenError(BoardConflictError):
    """A list's new stage is named like one the target board has (409 ``STAGE_NAME_TAKEN``)."""

    def __init__(self, *, group_id: str, stage_name: str) -> None:
        super().__init__(STAGE_NAME_TAKEN.format(name=stage_name))
        self.group_id = group_id
        self.stage_name = stage_name

    def body(self) -> Mapping[str, Any]:
        """The code, the first list whose new stage clashes, and the name it asked for."""
        return {
            "code": BoardErrorCode.STAGE_NAME_TAKEN,
            "group_id": self.group_id,
            "stage_name": self.stage_name,
        }


class ImportSourceDataError(BoardRuleError):
    """The source data can't be read, or the source refused the credentials."""


class ImportSourceUnavailableError(BoardStorageError):
    """The source didn't answer; trying again later may work."""
