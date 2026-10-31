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
sent, else an exponential backoff) and retries.
"""

import asyncio
from collections.abc import Mapping
from typing import Any
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
from app.services.imports.trello.throttle import RateLimiter, Sleep
from app.services.imports.trello.wire import (
    NOT_FOUND,
    TrelloCredentials,
    check_id,
    read_capped,
    retry_after,
)

REFUSED = "Trello refused the API key or token. Check them in Settings → Trello."
UNAVAILABLE = "Trello didn't answer. Try again in a minute."


class TrelloClient:
    """One importer's connection to Trello; close it when done."""

    def __init__(
        self,
        creds: TrelloCredentials,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        cfg = settings.boards
        self._http = httpx.AsyncClient(
            base_url=TRELLO_API_BASE,
            headers={"Authorization": creds.header()},
            timeout=cfg.trello_timeout_seconds,
            follow_redirects=False,
            transport=transport,
        )
        self._limiter = RateLimiter(cfg.trello_requests_per_10s, sleep=sleep)
        self._sleep = sleep

    async def aclose(self) -> None:
        """Close the HTTP connection pool."""
        await self._http.aclose()

    async def me(self) -> dict[str, Any]:
        """The member the token belongs to."""
        found = await self._json("/1/members/me", {"fields": "username,fullName"})
        return found if isinstance(found, dict) else {}

    async def boards(self) -> list[dict[str, Any]]:
        """The member's open boards."""
        found = await self._json("/1/members/me/boards", dict(TRELLO_BOARDS_PARAMS))
        return [b for b in found if isinstance(b, dict)] if isinstance(found, list) else []

    async def board(self, board_ref: str) -> dict[str, Any]:
        """The whole board in one nested read (lists, cards, labels, members, checklists)."""
        found = await self._json(
            f"/1/boards/{quote(board_ref, safe='')}", dict(TRELLO_BOARD_PARAMS)
        )
        if not isinstance(found, dict):
            raise ImportSourceDataError(NOT_FOUND)
        return found

    async def comments(self, board_id: str) -> list[dict[str, Any]]:
        """Every comment on the board, paged backwards with ``before`` and de-duplicated by id.

        Trello ignores ``page`` here; each page ends at its oldest action.
        """
        check_id(board_id)
        seen: set[str] = set()
        found: list[dict[str, Any]] = []
        before: str | None = None
        while True:
            params = {"filter": TRELLO_COMMENT_ACTION, "limit": str(TRELLO_ACTIONS_PAGE_LIMIT)}
            if before is not None:
                params["before"] = before
            page = await self._json(f"/1/boards/{board_id}/actions", params)
            rows = [a for a in page if isinstance(a, dict) and isinstance(a.get("id"), str)]
            fresh = [a for a in rows if a["id"] not in seen]
            seen.update(a["id"] for a in fresh)
            found.extend(fresh)
            if not fresh or len(rows) < TRELLO_ACTIONS_PAGE_LIMIT:
                return found
            before = rows[-1]["id"]

    async def download(
        self, card_id: str, attachment_id: str, name: str, limit: int
    ) -> bytes | None:
        """An uploaded attachment's bytes, or None when it's missing or over ``limit`` bytes.

        Read in chunks and abandoned as soon as it passes the limit, so an
        oversized file is never held in full.
        """
        check_id(card_id)
        check_id(attachment_id)
        filename = quote(name or "file", safe="")
        path = f"/1/cards/{card_id}/attachments/{attachment_id}/download/{filename}"
        for attempt in range(settings.boards.trello_max_retries + 1):
            await self._limiter.acquire()
            try:
                async with self._http.stream("GET", path) as resp:
                    if resp.status_code == httpx.codes.TOO_MANY_REQUESTS:
                        wait = retry_after(resp, attempt)
                    elif resp.status_code != httpx.codes.OK:
                        return None
                    else:
                        return await read_capped(resp, limit)
            except httpx.HTTPError:
                # The card keeps a link to the file instead.
                return None
            await self._sleep(wait)
        return None

    async def _json(self, path: str, params: Mapping[str, str]) -> Any:
        resp = await self._get(path, params)
        if resp.status_code in (httpx.codes.UNAUTHORIZED, httpx.codes.FORBIDDEN):
            raise ImportSourceDataError(REFUSED)
        if resp.status_code == httpx.codes.NOT_FOUND:
            raise ImportSourceDataError(NOT_FOUND)
        if resp.status_code != httpx.codes.OK:
            raise ImportSourceUnavailableError(UNAVAILABLE)
        try:
            return resp.json()
        except ValueError as exc:
            raise ImportSourceUnavailableError(UNAVAILABLE) from exc

    async def _get(self, path: str, params: Mapping[str, str]) -> httpx.Response:
        for attempt in range(settings.boards.trello_max_retries + 1):
            await self._limiter.acquire()
            request = self._http.build_request("GET", path, params=params)
            if request.url.host != TRELLO_API_HOST:
                raise ImportSourceDataError(NOT_FOUND)
            try:
                resp = await self._http.send(request)
            except httpx.HTTPError as exc:
                raise ImportSourceUnavailableError(UNAVAILABLE) from exc
            if resp.status_code != httpx.codes.TOO_MANY_REQUESTS:
                return resp
            await self._sleep(retry_after(resp, attempt))
        raise ImportSourceUnavailableError(UNAVAILABLE)


def new_client(creds: TrelloCredentials) -> TrelloClient:
    """A client for ``creds``; tests replace this to talk to a fake Trello."""
    return TrelloClient(creds)
