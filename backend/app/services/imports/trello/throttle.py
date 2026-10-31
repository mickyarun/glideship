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

"""A client-side limit on calls per time window, so Trello rarely answers 429.

Trello allows 100 requests per 10 seconds per token; the importer stays
under ``BoardsConfig.trello_requests_per_10s``. The clock and sleep are
injectable so tests run without waiting.
"""

import asyncio
import time
from collections import deque
from collections.abc import Awaitable, Callable

from app.services.imports.trello.constants import TRELLO_WINDOW_SECONDS

Sleep = Callable[[float], Awaitable[None]]


class RateLimiter:
    """At most ``limit`` acquisitions in any ``period`` seconds (a sliding window)."""

    def __init__(
        self,
        limit: int,
        period: float = TRELLO_WINDOW_SECONDS,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        if limit < 1:
            raise ValueError("a rate limit allows at least one call")
        self._limit = limit
        self._period = period
        self._clock = clock
        self._sleep = sleep
        self._stamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until another call fits in the window, then count it."""
        async with self._lock:
            now = self._clock()
            self._forget(now)
            if len(self._stamps) >= self._limit:
                await self._sleep(self._stamps[0] + self._period - now)
                # The oldest call has now left the window.
                self._stamps.popleft()
                now = max(self._clock(), now)
                self._forget(now)
            self._stamps.append(now)

    def _forget(self, now: float) -> None:
        while self._stamps and self._stamps[0] <= now - self._period:
            self._stamps.popleft()
