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

"""Run access checks a few at a time, retrying a failed one with backoff.

Every socket access check (subscribing and re-checking) goes through one
:class:`CheckSlots`, so a burst of re-checks waits for a slot instead of
taking every pooled database connection at once.
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

import structlog

logger = structlog.get_logger(__name__)

T = TypeVar("T")


class CheckSlots:
    """A bounded number of checks in flight, each tried up to ``attempts`` times."""

    def __init__(self, *, concurrency: int, attempts: int, first_delay: float) -> None:
        self._concurrency = concurrency
        self._attempts = attempts
        self._first_delay = first_delay
        self._loop: asyncio.AbstractEventLoop | None = None
        self._semaphore: asyncio.Semaphore | None = None

    def _slots(self) -> asyncio.Semaphore:
        # A semaphore belongs to the loop it first waits on; the process-wide
        # hub outlives a loop under tests, so each loop gets its own.
        loop = asyncio.get_running_loop()
        if self._semaphore is None or self._loop is not loop:
            self._loop, self._semaphore = loop, asyncio.Semaphore(self._concurrency)
        return self._semaphore

    async def run(self, check: Callable[[], Awaitable[T]], *, topic: str) -> T | None:
        """``check()``'s result, or None once every try has failed."""
        for attempt in range(1, self._attempts + 1):
            try:
                async with self._slots():
                    return await check()
            except Exception:  # noqa: BLE001 - logged; the caller decides what None means
                logger.warning("ws_recheck_failed", topic=topic, attempt=attempt, exc_info=True)
            if attempt < self._attempts:
                await asyncio.sleep(self._first_delay * 2 ** (attempt - 1))
        return None
