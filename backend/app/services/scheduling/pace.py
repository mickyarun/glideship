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


"""Pacing calls to a rate-limited API: a few at once, spaced out in time."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class Pace:
    """At most ``concurrency`` calls in flight, each starting ``interval_seconds`` after the last.

    One per rate-limited budget (for Slack, one per workspace per tick).
    The first call starts at once.
    """

    def __init__(self, concurrency: int, interval_seconds: float) -> None:
        """Set the limits."""
        self._slots = asyncio.Semaphore(concurrency)
        self._interval = interval_seconds
        self._lock = asyncio.Lock()
        self._next_start = 0.0

    @asynccontextmanager
    async def turn(self) -> AsyncIterator[None]:
        """Wait for a free slot and the next start time, then hold the slot."""
        async with self._slots:
            async with self._lock:
                now = asyncio.get_running_loop().time()
                wait = self._next_start - now
                self._next_start = max(now, self._next_start) + self._interval
            if wait > 0:
                await asyncio.sleep(wait)
            yield
