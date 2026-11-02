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


"""The pieces of a Trello call: credentials, id checks, waits between tries, capped reads."""

from dataclasses import dataclass

import httpx

from app.config import settings
from app.services.imports.errors import ImportSourceDataError, ImportSourceUnavailableError
from app.services.imports.trello.constants import TRELLO_ID_PATTERN

NOT_FOUND = "Trello has no such board, or the token can't read it."
REFUSED = "Trello refused the API key or token. Check them in Settings → Trello."
UNAVAILABLE = "Trello didn't answer. Try again in a minute."
_CHUNK = 64 * 1024


@dataclass(frozen=True)
class TrelloCredentials:
    """An API key and a user token."""

    api_key: str
    token: str

    def header(self) -> str:
        """The ``Authorization`` header Trello accepts for API calls and file downloads."""
        return f'OAuth oauth_consumer_key="{self.api_key}", oauth_token="{self.token}"'


def check_id(value: str) -> None:
    """Refuse anything not shaped like a Trello object id, before it reaches a URL."""
    if not TRELLO_ID_PATTERN.fullmatch(value):
        raise ImportSourceDataError(NOT_FOUND)


def backoff(attempt: int) -> float:
    """Seconds before retry ``attempt`` (0-based): doubling, never past the cap."""
    cfg = settings.boards
    return float(min(cfg.trello_backoff_seconds * 2**attempt, cfg.trello_max_wait_seconds))


def retry_after(resp: httpx.Response, attempt: int) -> float:
    """Seconds to wait after a 429: ``Retry-After`` when sent (capped), else :func:`backoff`."""
    header = resp.headers.get("Retry-After", "")
    if header.isdigit():
        return float(min(int(header), settings.boards.trello_max_wait_seconds))
    return backoff(attempt)


def wait_before_retry(resp: httpx.Response, attempt: int) -> float | None:
    """How long to wait before trying again, or None when the answer is final.

    A 429 waits as Trello asks; a 5xx is Trello having a bad moment and
    backs off. Anything else (success, refusal, not found) is final.
    """
    if resp.status_code == httpx.codes.TOO_MANY_REQUESTS:
        return retry_after(resp, attempt)
    if resp.status_code >= httpx.codes.INTERNAL_SERVER_ERROR:
        return backoff(attempt)
    return None


def check_status(resp: httpx.Response) -> None:
    """Refuse a final answer that isn't a 200, with a message for the importer."""
    if resp.status_code in (httpx.codes.UNAUTHORIZED, httpx.codes.FORBIDDEN):
        raise ImportSourceDataError(REFUSED)
    if resp.status_code == httpx.codes.NOT_FOUND:
        raise ImportSourceDataError(NOT_FOUND)
    if resp.status_code != httpx.codes.OK:
        raise ImportSourceUnavailableError(UNAVAILABLE)


async def read_capped(resp: httpx.Response, limit: int) -> bytes | None:
    """The body in chunks, or None as soon as it passes ``limit`` bytes."""
    declared = resp.headers.get("Content-Length", "")
    if declared.isdigit() and int(declared) > limit:
        return None
    data = bytearray()
    async for chunk in resp.aiter_bytes(_CHUNK):
        data.extend(chunk)
        if len(data) > limit:
            return None
    return bytes(data)
