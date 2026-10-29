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

"""Drop live subscriptions whose holder has lost access, one query per topic.

The hub keeps, for this process, every socket holding each revocable topic
(``ws_topic_policy.REVOCABLE_SCOPES``). It listens to the ``access:``
control topics as an event-bus transport, which has no bounded queue, so
a re-check request is never dropped. For each topic to re-check it asks
the scope's holder check once, for every named holder, against the
permissions stored in the database, and revokes the ones not returned.
Re-checks for one topic run one at a time; requests that arrive meanwhile
are merged into the next run. At most ``settings.ws.recheck_concurrency``
checks use the database at once, so an org-wide re-check can't drain the
connection pool.

A check that fails is retried with backoff (``settings.ws.recheck_*``).
If every try fails, the named holders are revoked: access fails closed.
A revoked client may subscribe again, and the subscribe check decides.

This assumes a single backend process, like the event bus and the socket
fan-out: a socket on another process would never hear the re-check.
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

import structlog

from app.api.v1.ws_check_slots import CheckSlots
from app.api.v1.ws_scope_checks import holders_still_allowed
from app.config import settings
from app.services.event_bus import register_transport
from app.services.ws_topic_policy import ACCESS_TOPIC_PREFIX, PEOPLE_ACCESS_SEGMENT

logger = structlog.get_logger(__name__)

HolderCheck = Callable[[str, str, set[str]], Awaitable[set[str]]]
_ACCESS = f"{ACCESS_TOPIC_PREFIX}:"
_PEOPLE = f"{_ACCESS}{PEOPLE_ACCESS_SEGMENT}:"


class Holder(Protocol):
    """A socket holding topics, as the hub needs to see it."""

    @property
    def user_id(self) -> str:
        """Whose socket it is."""
        ...

    @property
    def org_id(self) -> str:
        """The org they signed in to."""
        ...

    def revoke(self, topic: str) -> None:
        """Stop forwarding ``topic`` and tell the client why."""
        ...


class RevocationHub:
    """Every socket holding each revocable topic in this process."""

    def __init__(self, check: HolderCheck, slots: CheckSlots | None = None) -> None:
        self._check = check
        self._slots = slots or CheckSlots(
            concurrency=settings.ws.recheck_concurrency,
            attempts=settings.ws.recheck_attempts,
            first_delay=settings.ws.recheck_retry_delay_seconds,
        )
        self._held: dict[str, dict[Holder, None]] = {}
        self._pending: dict[str, set[str] | None] = {}
        self._workers: dict[str, asyncio.Task[None]] = {}

    def hold(self, topic: str, holder: Holder) -> None:
        """Watch ``topic`` for ``holder`` until :meth:`release`."""
        register_transport(self.on_publish)
        self._held.setdefault(topic, {})[holder] = None

    def release(self, topic: str, holder: Holder) -> None:
        """Stop watching ``topic`` for ``holder``."""
        holders = self._held.get(topic)
        if holders is not None:
            holders.pop(holder, None)
            if not holders:
                del self._held[topic]

    async def allows(self, topic: str, holder: Holder) -> bool:
        """Whether ``holder`` may hold ``topic`` now; False when the check keeps failing."""
        allowed = await self._allowed(topic, holder.org_id, {holder.user_id})
        return allowed is not None and holder.user_id in allowed

    async def on_publish(self, topic: str, data: dict[str, Any]) -> None:
        """Event-bus transport: queue re-checks named by control topics."""
        if not topic.startswith(_ACCESS):
            return
        users = data.get("user_ids")
        named = None if users is None else {str(u) for u in users}
        if topic.startswith(_PEOPLE):
            org = topic.removeprefix(_PEOPLE)
            targets = [t for t, hs in self._held.items() if any(h.org_id == org for h in hs)]
        else:
            targets = [topic.removeprefix(_ACCESS)]
        for target in targets:
            if target in self._held:
                self._queue(target, named)

    def _queue(self, topic: str, users: set[str] | None) -> None:
        if topic in self._pending:
            current = self._pending[topic]
            self._pending[topic] = None if users is None or current is None else current | users
        else:
            self._pending[topic] = users
        if topic not in self._workers:
            task = asyncio.create_task(self._work(topic), name=f"ws-recheck-{topic}")
            self._workers[topic] = task

    async def _work(self, topic: str) -> None:
        try:
            while topic in self._pending:
                users = self._pending.pop(topic)
                try:
                    await self._recheck(topic, users)
                except Exception:  # noqa: BLE001 - logged; the worker carries on
                    logger.exception("ws_recheck_crashed", topic=topic)
        finally:
            # No await between the last check and this, so a request queued
            # meanwhile either joined the loop or starts a new worker.
            self._workers.pop(topic, None)

    async def _recheck(self, topic: str, users: set[str] | None) -> None:
        holders = [h for h in self._held.get(topic, {}) if users is None or h.user_id in users]
        by_org: dict[str, list[Holder]] = {}
        for holder in holders:
            by_org.setdefault(holder.org_id, []).append(holder)
        for org, group in by_org.items():
            allowed = await self._allowed(topic, org, {h.user_id for h in group})
            if allowed is None:
                logger.warning("ws_recheck_failed_revoking", topic=topic, count=len(group))
                allowed = set()
            for holder in group:
                if holder.user_id not in allowed:
                    logger.info("ws_subscription_revoked", user_id=holder.user_id, topic=topic)
                    holder.revoke(topic)

    async def _allowed(self, topic: str, org: str, user_ids: set[str]) -> set[str] | None:
        """The check's answer, or None once every try has failed."""
        return await self._slots.run(lambda: self._check(topic, org, user_ids), topic=topic)


# The process-wide hub every socket registers with.
hub = RevocationHub(holders_still_allowed)
