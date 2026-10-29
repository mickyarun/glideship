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

"""Map a domain's error classes to HTTP statuses with one exception handler.

A domain (leave, boards) raises its own errors whose message is safe to
show; this turns them into ``{"detail": message}`` with the status from
its table, checked in order, so a subclass listed first wins.
"""

from collections.abc import Callable, Sequence

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

ErrorTable = Sequence[tuple[type[Exception], int]]
HeadersFor = Callable[[Exception], dict[str, str] | None]


def status_for(exc: Exception, table: ErrorTable) -> int:
    """The status the table gives ``exc`` (400 when no row matches)."""
    return next(
        (code for kind, code in table if isinstance(exc, kind)), status.HTTP_400_BAD_REQUEST
    )


def register_domain_errors(
    app: FastAPI,
    base: type[Exception],
    table: ErrorTable,
    *,
    headers: HeadersFor | None = None,
) -> None:
    """Answer every ``base`` error raised by a route from ``table``."""

    async def _respond(_request: Request, exc: Exception) -> JSONResponse:
        if not isinstance(exc, base):  # only ever registered for ``base``
            raise exc
        extra = headers(exc) if headers is not None else None
        return JSONResponse(
            {"detail": str(exc)}, status_code=status_for(exc, table), headers=extra
        )

    app.add_exception_handler(base, _respond)
