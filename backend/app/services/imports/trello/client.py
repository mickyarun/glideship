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


"""The Trello REST API, read-only, throttled, and only ever on ``api.trello.com``.

The key and token travel in the ``Authorization: OAuth`` header, never in
URLs, so they stay out of logs. Every path is built from ids the API gave
us, checked against Trello's id shape; redirects are not followed, so a
call can't be steered to another host. A 429 waits (``Retry-After`` when
sent, capped, else an exponential backoff), and a 5xx or a dropped
connection backs off; each up to ``trello_max_retries`` times. Every body
is read in chunks under a byte limit, so an oversized answer is never
held in full.
"""

import asyncio
import json
from collections.abc import Mapping
from types import TracebackType
from typing import Any, Self
from urllib.parse import quote

import httpx

from app.config import settings
from app.services.imports.errors import ImportSourceDataError, ImportSourceUnavailableError
from app.services.imports.trello.constants import (
    TRELLO_ACTIONS_PAGE_LIMIT,
    TRELLO_API_BASE,
    TRELLO_API_HOST,
    TRELLO_BOARD_PARAMS,
    TRELLO_BOARDS_PARAMS,
    TRELLO_COMMENT_ACTION,
)
from app.services.imports.trello.throttle import Sleep, limiter_for
from app.services.imports.trello.wire import (
    NOT_FOUND,
    UNAVAILABLE,
    TrelloCredentials,
    backoff,
    check_id,
    check_status,
    read_capped,
    wait_before_retry,
)

TOO_BIG = "This Trello board is larger than the import limit."


class TrelloClient:
    """One importer's connection to Trello; use it as an async context manager."""

    def __init__(
        self,
        creds: TrelloCredentials,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._http = httpx.AsyncClient(
            base_url=TRELLO_API_BASE,
            headers={"Authorization": creds.header()},
            timeout=settings.boards.trello_timeout_seconds,
            follow_redirects=False,
            transport=transport,
        )
        self._limiter = limiter_for(creds.token)
        self._sleep = sleep

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self, kind: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the HTTP connection pool."""
        await self._http.aclose()

    async def me(self) -> dict[str, Any]:
        """The member the token belongs to."""
        found, _ = await self._json("/1/members/me", {"fields": "username,fullName"}, _reply_cap())
        return found if isinstance(found, dict) else {}

    async def boards(self) -> list[dict[str, Any]]:
        """The member's open boards."""
        found, _ = await self._json(
            "/1/members/me/boards", dict(TRELLO_BOARDS_PARAMS), _reply_cap()
        )
        return [b for b in found if isinstance(b, dict)] if isinstance(found, list) else []

    async def board(self, board_ref: str, limit: int) -> tuple[dict[str, Any], int]:
        """The whole board in one nested read, and its size; at most ``limit`` bytes."""
        path = f"/1/boards/{quote(board_ref, safe='')}"
        found, size = await self._json(path, dict(TRELLO_BOARD_PARAMS), limit)
        if not isinstance(found, dict):
            raise ImportSourceDataError(NOT_FOUND)
        return found, size

    async def comments(self, board_id: str, limit: int, max_items: int) -> list[dict[str, Any]]:
        """Every comment, paged back with ``before`` and de-duplicated by id.

        Trello ignores ``page`` here; each page ends at its oldest action.
        All pages together stay within ``limit`` bytes and ``max_items``.
        """
        check_id(board_id)
        seen: set[str] = set()
        found: list[dict[str, Any]] = []
        before: str | None = None
        while True:
            params = {"filter": TRELLO_COMMENT_ACTION, "limit": str(TRELLO_ACTIONS_PAGE_LIMIT)}
            if before is not None:
                params["before"] = before
            page, size = await self._json(f"/1/boards/{board_id}/actions", params, limit)
            limit -= size
            rows = [a for a in _rows(page) if isinstance(a.get("id"), str)]
            fresh = [a for a in rows if a["id"] not in seen]
            seen.update(a["id"] for a in fresh)
            found.extend(fresh)
            if len(found) > max_items:
                raise ImportSourceDataError(TOO_BIG)
            if not fresh or len(rows) < TRELLO_ACTIONS_PAGE_LIMIT:
                return found
            before = rows[-1]["id"]

    async def download(
        self, card_id: str, attachment_id: str, name: str, limit: int
    ) -> bytes | None:
        """An uploaded attachment's bytes, or None when it's missing, refused or over ``limit``.

        The card keeps a link to the file instead.
        """
        check_id(card_id)
        check_id(attachment_id)
        filename = quote(name or "file", safe="")
        path = f"/1/cards/{card_id}/attachments/{attachment_id}/download/{filename}"
        try:
            return await self._fetch(path, {}, limit)
        except (ImportSourceDataError, ImportSourceUnavailableError):
            return None

    async def _json(self, path: str, params: Mapping[str, str], limit: int) -> tuple[Any, int]:
        body = await self._fetch(path, params, limit)
        if body is None:
            raise ImportSourceDataError(TOO_BIG)
        try:
            return await asyncio.to_thread(json.loads, body), len(body)
        except (ValueError, RecursionError) as exc:
            raise ImportSourceUnavailableError(UNAVAILABLE) from exc

    async def _fetch(self, path: str, params: Mapping[str, str], limit: int) -> bytes | None:
        """A 200 answer's body (None past ``limit``), after any waits and retries."""
        retries = settings.boards.trello_max_retries
        for attempt in range(retries + 1):
            await self._limiter.acquire()
            request = self._http.build_request("GET", path, params=params)
            if request.url.host != TRELLO_API_HOST:
                raise ImportSourceDataError(NOT_FOUND)
            try:
                resp = await self._http.send(request, stream=True)
                try:
                    wait = wait_before_retry(resp, attempt)
                    if wait is None:
                        check_status(resp)
                        return await read_capped(resp, limit)
                finally:
                    await resp.aclose()
            except httpx.HTTPError:
                wait = backoff(attempt)
            if attempt < retries:
                await self._sleep(wait)
        raise ImportSourceUnavailableError(UNAVAILABLE)


def _rows(page: Any) -> list[dict[str, Any]]:
    return [a for a in page if isinstance(a, dict)] if isinstance(page, list) else []


def _reply_cap() -> int:
    # Member and board-list reads share the snapshot cap; they're far below it.
    return settings.boards.import_max_snapshot_bytes


def new_client(creds: TrelloCredentials) -> TrelloClient:
    """A client for ``creds``; tests replace this to talk to a fake Trello."""
    return TrelloClient(creds)
