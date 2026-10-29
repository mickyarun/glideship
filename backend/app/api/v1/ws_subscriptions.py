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

"""One socket's topic subscriptions.

Each subscription reads its event-bus queue into the socket's send queue.
Revocable topics are also registered with the process-wide
:class:`~app.api.v1.ws_revocation.RevocationHub`, which revokes them when a
re-check finds the holder has lost access. :meth:`ConnectionSubscriptions.add`
registers with the hub and the event bus first, then confirms access
against the stored permissions, and only then starts forwarding: a
revocation committed while the socket was subscribing isn't missed, and
nothing reaches the client before access is confirmed.

An event published alongside an access change names whose access changed
(``ws_topic_policy.ACCESS_CHANGED_KEY``). The reader confirms access again
before forwarding it to anyone named, so a person removed from a board
doesn't receive the event that removed them.
"""

import asyncio
from typing import Any

import structlog

from app.api.v1.ws_revocation import RevocationHub, hub
from app.services.event_bus import subscribe, unsubscribe
from app.services.ws_topic_policy import ACCESS_CHANGED_KEY, Subscriber, access_topic

logger = structlog.get_logger(__name__)

Queue = asyncio.Queue[dict[str, Any]]


class ConnectionSubscriptions:
    """The topics one socket holds, each with its reader task."""

    def __init__(
        self, who: Subscriber, send_queue: Queue, revocations: RevocationHub = hub
    ) -> None:
        self._who = who
        self._send = send_queue
        self._hub = revocations
        # A topic's task is None until access is confirmed.
        self._readers: dict[str, tuple[Queue, asyncio.Task[None] | None]] = {}

    @property
    def user_id(self) -> str:
        """Whose socket this is."""
        return self._who.user_id

    @property
    def org_id(self) -> str:
        """The org the socket signed in to."""
        return self._who.org_id

    @property
    def topics(self) -> frozenset[str]:
        """The topics this socket currently holds."""
        return frozenset(self._readers)

    async def add(self, topic: str) -> bool:
        """Start forwarding ``topic``; the caller has already run the scope check.

        For a revocable topic, access is confirmed again once the hub is
        watching, before anything is forwarded; False (and nothing held)
        when that confirmation fails.
        """
        if topic in self._readers:
            return True
        revocable = access_topic(topic) is not None
        if revocable:
            self._hub.hold(topic, self)
        queue = subscribe(topic)
        self._readers[topic] = (queue, None)
        if revocable and not await self._hub.allows(topic, self):
            self.remove(topic)
            return False
        if self._readers.get(topic) != (queue, None):
            return False  # revoked or removed while access was being confirmed
        task = asyncio.create_task(self._read(topic, queue), name=f"ws-reader-{topic}")
        self._readers[topic] = (queue, task)
        return True

    def remove(self, topic: str) -> bool:
        """Stop forwarding ``topic``; False when it wasn't held."""
        reader = self._readers.pop(topic, None)
        if reader is None:
            return False
        queue, task = reader
        if task is not None:
            task.cancel()
        unsubscribe(topic, queue)
        self._hub.release(topic, self)
        return True

    def revoke(self, topic: str) -> None:
        """Drop ``topic`` because access was lost, and tell the client."""
        if self.remove(topic):
            self._put(topic, {"topic": topic, "error": "revoked"})

    def close(self) -> None:
        """Drop every subscription."""
        for topic in list(self._readers):
            self.remove(topic)

    async def _read(self, topic: str, queue: Queue) -> None:
        try:
            while True:
                envelope = await queue.get()
                if "agent_activity" in topic:
                    evt = envelope.get("data", {}).get("event_type", "")
                    logger.info("ws_forwarding_agent_event", topic=topic, event_type=evt)
                forward = await self._confirmed(topic, envelope)
                if forward is None:
                    self.revoke(topic)
                    return
                self._put(topic, forward)
        except asyncio.CancelledError:
            pass

    async def _confirmed(self, topic: str, envelope: dict[str, Any]) -> dict[str, Any] | None:
        """The envelope to forward, or None when its access change took this socket's away."""
        data = envelope.get("data")
        if not isinstance(data, dict) or ACCESS_CHANGED_KEY not in data:
            return envelope
        named = data[ACCESS_CHANGED_KEY]
        if (named is None or self.user_id in named) and not await self._hub.allows(topic, self):
            return None
        rest = {k: v for k, v in data.items() if k != ACCESS_CHANGED_KEY}
        return {**envelope, "data": rest}

    def _put(self, topic: str, message: dict[str, Any]) -> None:
        try:
            self._send.put_nowait(message)
        except asyncio.QueueFull:
            # A revoke still takes effect: the subscription is already gone.
            logger.warning("ws_send_queue_full", user_id=self._who.user_id, topic=topic)
