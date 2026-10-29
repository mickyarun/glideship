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

"""Sockets drop revocable subscriptions when a re-check says access is gone.

The hub runs one holder check per topic for every holder named, against a
fake check here; the real one is covered by the board integration tests.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest

from app.api.v1.ws_revocation import RevocationHub
from app.api.v1.ws_subscriptions import ConnectionSubscriptions
from app.services import event_bus
from app.services.ws_topic_policy import Subscriber, access_topic, people_access_topic

ORG = str(uuid.uuid4())
QUIET = 0.2


class _Check:
    """A holder check that allows ``allowed`` and records each call."""

    def __init__(self) -> None:
        self.allowed: set[str] | None = None  # None: allow everyone asked about
        self.calls: list[set[str]] = []
        self.failures = 0

    async def __call__(self, topic: str, org: str, users: set[str]) -> set[str]:
        self.calls.append(set(users))
        if self.failures:
            self.failures -= 1
            raise RuntimeError("database unavailable")
        return set(users) if self.allowed is None else users & self.allowed


def _who() -> Subscriber:
    return Subscriber(user_id=str(uuid.uuid4()), org_id=ORG, has_engineering=False)


async def _next(queue: asyncio.Queue[dict[str, Any]]) -> dict[str, Any]:
    return await asyncio.wait_for(queue.get(), timeout=1)


async def _nothing_arrives(queue: asyncio.Queue[dict[str, Any]]) -> None:
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(queue.get(), timeout=QUIET)


async def _until(condition: Any) -> None:
    for _ in range(100):
        if condition():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition never held")


@pytest.fixture
def topic() -> str:
    return f"board:{uuid.uuid4()}"


def _control(topic: str) -> str:
    control = access_topic(topic)
    assert control is not None
    return control


async def _socket(
    hub: RevocationHub, topic: str, who: Subscriber | None = None, maxsize: int = 0
) -> tuple[ConnectionSubscriptions, asyncio.Queue[dict[str, Any]]]:
    send: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=maxsize)
    subs = ConnectionSubscriptions(who or _who(), send, hub)
    assert await subs.add(topic)
    return subs, send


async def test_a_failed_recheck_revokes_and_stops_forwarding(topic: str) -> None:
    check = _Check()
    hub = RevocationHub(check)
    subs, send = await _socket(hub, topic)
    event_bus.publish(topic, {"event": "card_created"})
    assert (await _next(send))["data"] == {"event": "card_created"}

    check.allowed = set()
    event_bus.publish(_control(topic), {"user_ids": [subs.user_id]})
    assert await _next(send) == {"topic": topic, "error": "revoked"}
    assert subs.topics == frozenset()
    event_bus.publish(topic, {"event": "card_updated"})
    await _nothing_arrives(send)


async def test_one_check_per_topic_covers_every_holder_named(topic: str) -> None:
    check = _Check()
    hub = RevocationHub(check)
    sockets = [await _socket(hub, topic) for _ in range(3)]
    check.calls.clear()
    (keep, _), (drop, drop_send), (other, _) = sockets
    check.allowed = {keep.user_id, other.user_id}

    event_bus.publish(_control(topic), {"user_ids": None})
    assert await _next(drop_send) == {"topic": topic, "error": "revoked"}
    assert check.calls == [{keep.user_id, drop.user_id, other.user_id}]
    assert keep.topics == other.topics == frozenset({topic})

    event_bus.publish(_control(topic), {"user_ids": [str(uuid.uuid4())]})
    await asyncio.sleep(QUIET)
    assert len(check.calls) == 1  # nobody holding the topic was named


async def test_a_people_recheck_covers_every_revocable_topic_they_hold() -> None:
    check = _Check()
    hub = RevocationHub(check)
    who = _who()
    first, second = f"board:{uuid.uuid4()}", f"board:{uuid.uuid4()}"
    send: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    subs = ConnectionSubscriptions(who, send, hub)
    assert await subs.add(first) and await subs.add(second)
    assert await subs.add(f"notifications:{who.user_id}")
    check.allowed = set()
    event_bus.publish(people_access_topic(ORG), {"user_ids": [who.user_id]})
    revoked = {(await _next(send))["topic"], (await _next(send))["topic"]}
    assert revoked == {first, second}
    assert subs.topics == frozenset({f"notifications:{who.user_id}"})


async def test_subscribing_confirms_access_once_the_hub_is_watching(topic: str) -> None:
    check = _Check()
    check.allowed = set()
    subs = ConnectionSubscriptions(_who(), asyncio.Queue(), RevocationHub(check))
    assert not await subs.add(topic)
    assert subs.topics == frozenset()


async def test_a_full_send_queue_still_revokes(topic: str) -> None:
    check = _Check()
    hub = RevocationHub(check)
    subs, send = await _socket(hub, topic, maxsize=1)
    send.put_nowait({"filler": True})
    check.allowed = set()
    event_bus.publish(_control(topic), {"user_ids": None})
    await _until(lambda: subs.topics == frozenset())


async def test_closed_sockets_are_no_longer_checked(topic: str) -> None:
    check = _Check()
    hub = RevocationHub(check)
    subs, _ = await _socket(hub, topic)
    subs.close()
    check.calls.clear()
    event_bus.publish(_control(topic), {"user_ids": None})
    await asyncio.sleep(QUIET)
    assert check.calls == []


def test_only_revocable_scopes_have_a_control_topic() -> None:
    assert access_topic("board:abc") == "access:board:abc"
    assert access_topic("notifications:abc") is None
    assert access_topic("access:board:abc") is None
