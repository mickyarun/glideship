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

"""Import errors, on the board error classes so the boards API maps them to HTTP."""

from app.services.boards.errors import (
    BoardConflictError,
    BoardItemNotFoundError,
    BoardRuleError,
    BoardStorageError,
)

IMPORT_NOT_FOUND = "Import not found."


class ImportNotFoundError(BoardItemNotFoundError):
    """No such import in the org, or the caller didn't start it."""

    def __init__(self) -> None:
        super().__init__(IMPORT_NOT_FOUND)


class ImportStateError(BoardConflictError):
    """The import isn't at a step where this can happen."""


class ImportSourceDataError(BoardRuleError):
    """The source data can't be read, or the source refused the credentials."""


class ImportSourceUnavailableError(BoardStorageError):
    """The source didn't answer; trying again later may work."""
