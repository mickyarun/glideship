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

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.services.boards.errors import (
    BoardActionForbiddenError,
    BoardConflictError,
    BoardError,
    BoardItemNotFoundError,
    BoardRuleError,
    BoardTooLargeError,
)

_STATUS: tuple[tuple[type[BoardError], int], ...] = (
    (BoardItemNotFoundError, status.HTTP_404_NOT_FOUND),
    (BoardActionForbiddenError, status.HTTP_403_FORBIDDEN),
    (BoardConflictError, status.HTTP_409_CONFLICT),
    (BoardRuleError, status.HTTP_422_UNPROCESSABLE_ENTITY),
    (BoardTooLargeError, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE),
)


def status_for(exc: BoardError) -> int:
    """The HTTP status for a board error (400 for an unclassified one)."""
    return next((code for kind, code in _STATUS if isinstance(exc, kind)), 400)


async def _respond(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, BoardError):  # only ever registered for BoardError
        raise exc
    return JSONResponse({"detail": str(exc)}, status_code=status_for(exc))


def register_board_errors(app: FastAPI) -> None:
    """Install the handler; call once wherever the API router is mounted."""
    app.add_exception_handler(BoardError, _respond)
