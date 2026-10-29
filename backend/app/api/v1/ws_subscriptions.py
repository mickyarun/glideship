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

"""One socket's topic subscriptions, and dropping them when access is lost.

Each subscription reads its event-bus queue into the socket's send queue.
A topic whose scope can be revoked (``ws_topic_policy.REVOCABLE_SCOPES``)
also listens on its ``access:`` control topic; when a service asks for a
re-check that names this caller (or everyone), the subscription is checked
again with the same scope check that admitted it, and dropped if it fails.
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import structlog

from app.services.event_bus import subscribe, unsubscribe
from app.services.ws_topic_policy import Subscriber, access_topic

logger = structlog.get_logger(__name__)

Queue = asyncio.Queue[dict[str, Any]]
ScopeCheck = Callable[[str, Subscriber], Awaitable[bool]]


class ConnectionSubscriptions:
    """The topics one socket holds, each with its reader tasks."""

    def __init__(self, who: Subscriber, send_queue: Queue, check: ScopeCheck) -> None:
        self._who = who
        self._send = send_queue
        self._check = check
        # topic → [(bus topic, queue, reader task)], the topic's own first.
        self._readers: dict[str, list[tuple[str, Queue, asyncio.Task[None]]]] = {}

    @property
    def topics(self) -> frozenset[str]:
        """The topics this socket currently holds."""
        return frozenset(self._readers)

    def add(self, topic: str) -> None:
        """Start forwarding ``topic``; the caller has already checked access."""
        if topic in self._readers:
            return
        readers = [self._start(topic, topic, self._forward)]
        control = access_topic(topic)
        if control is not None:
            readers.append(self._start(topic, control, self._recheck))
        self._readers[topic] = readers

    def remove(self, topic: str) -> bool:
        """Stop forwarding ``topic``; False when it wasn't held."""
        readers = self._readers.pop(topic, None)
        if readers is None:
            return False
        for bus_topic, queue, task in readers:
            task.cancel()
            unsubscribe(bus_topic, queue)
        return True

    def close(self) -> None:
        """Drop every subscription."""
        for topic in list(self._readers):
            self.remove(topic)

    def _start(
        self,
        topic: str,
        bus_topic: str,
        handle: Callable[[str, dict[str, Any]], Awaitable[None]],
    ) -> tuple[str, Queue, asyncio.Task[None]]:
        queue = subscribe(bus_topic)
        task = asyncio.create_task(self._read(topic, queue, handle), name=f"ws-reader-{bus_topic}")
        return bus_topic, queue, task

    async def _read(
        self,
        topic: str,
        queue: Queue,
        handle: Callable[[str, dict[str, Any]], Awaitable[None]],
    ) -> None:
        try:
            while True:
                await handle(topic, await queue.get())
        except asyncio.CancelledError:
            pass

    async def _forward(self, topic: str, envelope: dict[str, Any]) -> None:
        if "agent_activity" in topic:
            evt = envelope.get("data", {}).get("event_type", "")
            logger.info("ws_forwarding_agent_event", topic=topic, event_type=evt)
        self._put(topic, envelope)

    async def _recheck(self, topic: str, envelope: dict[str, Any]) -> None:
        users = envelope.get("data", {}).get("user_ids")
        if users is not None and self._who.user_id not in users:
            return
        try:
            allowed = await self._check(topic, self._who)
        except Exception:  # noqa: BLE001 - an unanswerable check fails closed
            logger.exception("ws_recheck_failed", user_id=self._who.user_id, topic=topic)
            allowed = False
        if allowed:
            return
        logger.info("ws_subscription_revoked", user_id=self._who.user_id, topic=topic)
        self._put(topic, {"topic": topic, "error": "revoked"})
        # Cancels this reader too, so it must be the last thing it does.
        self.remove(topic)

    def _put(self, topic: str, message: dict[str, Any]) -> None:
        try:
            self._send.put_nowait(message)
        except asyncio.QueueFull:
            logger.warning("ws_send_queue_full", user_id=self._who.user_id, topic=topic)
