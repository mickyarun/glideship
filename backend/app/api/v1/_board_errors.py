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

"""Turn board domain errors into HTTP responses, in one place."""

from fastapi import FastAPI, status

from app.api.v1._domain_errors import ErrorTable, register_domain_errors
from app.api.v1._domain_errors import status_for as _status_for
from app.services.boards.errors import (
    BoardActionForbiddenError,
    BoardConflictError,
    BoardError,
    BoardItemNotFoundError,
    BoardRuleError,
    BoardStorageError,
    BoardTooLargeError,
)

_STATUS: ErrorTable = (
    (BoardItemNotFoundError, status.HTTP_404_NOT_FOUND),
    (BoardActionForbiddenError, status.HTTP_403_FORBIDDEN),
    (BoardConflictError, status.HTTP_409_CONFLICT),
    (BoardRuleError, status.HTTP_422_UNPROCESSABLE_ENTITY),
    (BoardTooLargeError, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE),
    (BoardStorageError, status.HTTP_502_BAD_GATEWAY),
)


def status_for(exc: BoardError) -> int:
    """The HTTP status for a board error (400 for an unclassified one)."""
    return _status_for(exc, _STATUS)


def register_board_errors(app: FastAPI) -> None:
    """Install the handler; call once wherever the API router is mounted."""
    register_domain_errors(app, BoardError, _STATUS)
