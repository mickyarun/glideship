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

"""The pieces of a Trello call: credentials, id checks, 429 waits, capped reads."""

from dataclasses import dataclass

import httpx

from app.config import settings
from app.services.imports.errors import ImportSourceDataError
from app.services.imports.trello.constants import TRELLO_ID_PATTERN

NOT_FOUND = "Trello has no such board, or the token can't read it."
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


def retry_after(resp: httpx.Response, attempt: int) -> float:
    """Seconds to wait after a 429: ``Retry-After`` when sent, else doubling backoff."""
    header = resp.headers.get("Retry-After", "")
    if header.isdigit():
        return float(header)
    return float(settings.boards.trello_backoff_seconds * 2**attempt)


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
