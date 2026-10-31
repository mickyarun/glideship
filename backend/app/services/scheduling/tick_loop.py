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

"""A scheduler's loop, and when a daily local-time message is due (no I/O in the latter).

Schedulers tick on a fixed interval and recompute local times on every
pass, so they stay right across DST changes and catch up after a restart.
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import date, datetime, time, timedelta, tzinfo

import structlog

logger = structlog.get_logger(__name__)

# A daily message is due from its local time until this long after, so a
# late restart still sends it but never sends the morning message at night.
LATEST_AFTER = timedelta(hours=3)


async def run_tick_loop(
    name: str, tick_seconds: float, tick_once: Callable[[], Awaitable[None]]
) -> None:
    """Call ``tick_once`` every ``tick_seconds`` until cancelled.

    A failed tick is logged as ``<name>_tick_failed`` and the loop carries on.
    """
    while True:
        try:
            await tick_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(f"{name}_tick_failed")
        await asyncio.sleep(tick_seconds)


def due_local_date(
    now_utc: datetime, zone: tzinfo, post_time: str | time, *, window: timedelta
) -> date | None:
    """The local date whose message is due now, or None outside the window.

    The window runs from ``post_time`` for ``window`` on the same local
    date, so it ends at local midnight however long it is. A scheduler that
    was down for less than the window sends late the same day; one down
    for longer skips that day.

    ``post_time`` is a local time, or one written ``"HH:MM"``.
    """
    local = now_utc.astimezone(zone)
    at = post_time if isinstance(post_time, time) else _clock(post_time)
    start = datetime.combine(local.date(), time(at.hour, at.minute), tzinfo=zone)
    return local.date() if start <= local < start + window else None


def _clock(text: str) -> time:
    hour, minute = (int(part) for part in text.split(":"))
    return time(hour, minute)
