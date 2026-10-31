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

"""The Trello client against a fake Trello: paging, backoff, the throttle and downloads."""

from collections.abc import Callable

import httpx
import pytest

from app.config import settings
from app.services.imports.errors import ImportSourceDataError, ImportSourceUnavailableError
from app.services.imports.trello.client import TrelloClient
from app.services.imports.trello.constants import TRELLO_ACTIONS_PAGE_LIMIT, TRELLO_API_HOST
from app.services.imports.trello.throttle import RateLimiter
from app.services.imports.trello.wire import TrelloCredentials

CREDS = TrelloCredentials(api_key="key-123", token="token-456")
BOARD = "5f0000000000000000000b01"
CARD = "5f00000000000000000c0001"
FILE = "5f00000000000000000f0002"
Handler = Callable[[httpx.Request], httpx.Response]


class Recorder:
    """Every request the fake Trello saw, and every wait the client asked for."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.sleeps: list[float] = []

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)

    def client(self, handler: Handler) -> TrelloClient:
        def record(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return handler(request)

        return TrelloClient(CREDS, transport=httpx.MockTransport(record), sleep=self.sleep)


def _action(n: int) -> dict[str, object]:
    return {"id": f"{n:024x}", "type": "commentCard", "data": {"text": f"c{n}"}}


async def test_comments_page_back_with_before_and_drop_repeats() -> None:
    first = [_action(n) for n in range(TRELLO_ACTIONS_PAGE_LIMIT, 0, -1)]
    # The second page repeats the boundary action, as Trello may.
    second = [_action(1), _action(0)]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=second if "before" in request.url.params else first)

    rec = Recorder()
    client = rec.client(handler)
    found = await client.comments(BOARD)
    await client.aclose()
    assert len(found) == TRELLO_ACTIONS_PAGE_LIMIT + 1
    assert len({a["id"] for a in found}) == len(found)
    assert rec.requests[1].url.params["before"] == first[-1]["id"]
    assert rec.requests[0].url.params["filter"] == "commentCard"
    for request in rec.requests:
        assert request.url.host == TRELLO_API_HOST
        # Credentials travel in the header, never in the URL.
        assert "token-456" not in str(request.url) and "key-123" not in str(request.url)
        assert request.headers["Authorization"] == (
            'OAuth oauth_consumer_key="key-123", oauth_token="token-456"'
        )


async def test_a_429_waits_retry_after_then_backs_off_and_gives_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings.boards, "trello_max_retries", 2)
    monkeypatch.setattr(settings.boards, "trello_backoff_seconds", 1.5)
    answers = [httpx.Response(429, headers={"Retry-After": "3"}), httpx.Response(200, json={})]
    rec = Recorder()
    client = rec.client(lambda _: answers.pop(0))
    assert await client.me() == {}
    assert rec.sleeps == [3.0]

    rec = Recorder()
    client = rec.client(lambda _: httpx.Response(429))
    with pytest.raises(ImportSourceUnavailableError):
        await client.me()
    assert rec.sleeps == [1.5, 3.0, 6.0] and len(rec.requests) == 3


async def test_refused_credentials_and_missing_boards_read_as_bad_data() -> None:
    rec = Recorder()
    with pytest.raises(ImportSourceDataError):
        await rec.client(lambda _: httpx.Response(401)).me()
    with pytest.raises(ImportSourceDataError):
        await rec.client(lambda _: httpx.Response(404)).board(BOARD)
    with pytest.raises(ImportSourceUnavailableError):
        await rec.client(lambda _: httpx.Response(500)).boards()
    with pytest.raises(ImportSourceDataError):
        await rec.client(lambda _: httpx.Response(200, json=[])).comments("../../evil")
    assert all(r.url.host == TRELLO_API_HOST for r in rec.requests)


async def test_downloads_use_the_attachment_endpoint_and_stop_at_the_cap() -> None:
    body = b"x" * 100

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    rec = Recorder()
    client = rec.client(handler)
    assert await client.download(CARD, FILE, "mock file.png", limit=100) == body
    request = rec.requests[0]
    assert request.url.host == TRELLO_API_HOST
    assert request.url.raw_path.decode() == (
        f"/1/cards/{CARD}/attachments/{FILE}/download/mock%20file.png"
    )
    assert await client.download(CARD, FILE, "mock.png", limit=99) is None
    with pytest.raises(ImportSourceDataError):
        await client.download("https://evil.example", FILE, "x", limit=100)

    redirect = rec.client(
        lambda _: httpx.Response(302, headers={"Location": "https://evil.example/"})
    )
    # Redirects are never followed, so the file stays a link.
    assert await redirect.download(CARD, FILE, "mock.png", limit=100) is None
    assert all(r.url.host == TRELLO_API_HOST for r in rec.requests)


async def test_the_limiter_waits_once_the_window_is_full() -> None:
    now = [0.0]
    waits: list[float] = []

    async def sleep(seconds: float) -> None:
        waits.append(seconds)
        now[0] += seconds

    limiter = RateLimiter(2, 10.0, clock=lambda: now[0], sleep=sleep)
    for _ in range(2):
        await limiter.acquire()
    now[0] = 4.0
    await limiter.acquire()
    assert waits == [6.0]
    now[0] = 30.0
    await limiter.acquire()
    assert waits == [6.0]
