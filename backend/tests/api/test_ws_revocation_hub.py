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

"""How the hub behaves when checks fail, crash, pile up or race a subscribe."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest

from app.api.v1 import ws_revocation
from app.api.v1.ws_check_slots import CheckSlots
from app.api.v1.ws_revocation import RevocationHub
from app.api.v1.ws_subscriptions import ConnectionSubscriptions
from app.services import event_bus
from app.services.ws_topic_policy import (
    ACCESS_CHANGED_KEY,
    Subscriber,
    access_topic,
    people_access_topic,
)

ORG = str(uuid.uuid4())
QUIET = 0.2
Queue = asyncio.Queue[dict[str, Any]]


class _Check:
    """Allows ``allowed`` (everyone when None), fails ``failures`` times, can be held."""

    def __init__(self) -> None:
        self.allowed: set[str] | None = None
        self.failures = 0
        self.calls = 0
        self.in_flight = 0
        self.most_in_flight = 0
        self.gate: asyncio.Event | None = None

    async def __call__(self, topic: str, org: str, users: set[str]) -> set[str]:
        self.calls += 1
        self.in_flight += 1
        self.most_in_flight = max(self.most_in_flight, self.in_flight)
        try:
            if self.gate is not None:
                await self.gate.wait()
            if self.failures:
                self.failures -= 1
                raise RuntimeError("database unavailable")
            return set(users) if self.allowed is None else users & self.allowed
        finally:
            self.in_flight -= 1


class _Log:
    """Stands in for the hub's logger and records each event name."""

    def __init__(self) -> None:
        self.events: list[str] = []

    def _record(self, event: str, *args: Any, **kw: Any) -> None:
        self.events.append(event)

    info = warning = exception = error = _record


def _hub(check: _Check, concurrency: int = 4) -> RevocationHub:
    return RevocationHub(check, CheckSlots(concurrency=concurrency, attempts=3, first_delay=0))


def _who() -> Subscriber:
    return Subscriber(user_id=str(uuid.uuid4()), org_id=ORG, has_engineering=False)


def _control(topic: str) -> str:
    control = access_topic(topic)
    assert control is not None
    return control


async def _socket(hub: RevocationHub, topic: str) -> tuple[ConnectionSubscriptions, Queue]:
    send: Queue = asyncio.Queue()
    subs = ConnectionSubscriptions(_who(), send, hub)
    assert await subs.add(topic)
    return subs, send


async def _next(queue: Queue) -> dict[str, Any]:
    return await asyncio.wait_for(queue.get(), timeout=1)


async def _nothing_arrives(queue: Queue) -> None:
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


async def test_a_check_that_keeps_failing_revokes_after_every_try(topic: str) -> None:
    check = _Check()
    subs, send = await _socket(_hub(check), topic)
    check.calls, check.failures = 0, 99
    event_bus.publish(_control(topic), {"user_ids": None})
    assert await _next(send) == {"topic": topic, "error": "revoked"}
    assert check.calls == 3
    assert subs.topics == frozenset()


async def test_a_check_that_recovers_within_the_tries_keeps_access(topic: str) -> None:
    check = _Check()
    subs, send = await _socket(_hub(check), topic)
    check.calls, check.failures = 0, 2
    event_bus.publish(_control(topic), {"user_ids": None})
    await _until(lambda: check.calls == 3)
    await _nothing_arrives(send)
    assert subs.topics == frozenset({topic})


async def test_checks_in_flight_never_exceed_the_concurrency(topic: str) -> None:
    check = _Check()
    hub = _hub(check, concurrency=2)
    sockets = [await _socket(hub, f"board:{uuid.uuid4()}") for _ in range(6)]
    check.gate, check.most_in_flight = asyncio.Event(), 0
    for subs, _ in sockets:
        event_bus.publish(people_access_topic(ORG), {"user_ids": [subs.user_id]})
    await _until(lambda: check.in_flight == 2)
    await asyncio.sleep(QUIET)
    assert check.most_in_flight == 2
    check.gate.set()
    await _until(lambda: check.calls == 6 + 6)
    assert check.most_in_flight == 2


@pytest.mark.parametrize("allowed", [True, False])
async def test_nothing_is_forwarded_until_access_is_confirmed(topic: str, allowed: bool) -> None:
    check = _Check()
    check.gate, check.allowed = asyncio.Event(), None if allowed else set()
    send: Queue = asyncio.Queue()
    subs = ConnectionSubscriptions(_who(), send, _hub(check))
    adding = asyncio.create_task(subs.add(topic))
    await _until(lambda: check.in_flight == 1)
    event_bus.publish(topic, {"event": "card_created"})
    await _nothing_arrives(send)
    check.gate.set()
    assert await adding is allowed
    if allowed:
        assert (await _next(send))["data"] == {"event": "card_created"}
    await _nothing_arrives(send)
    subs.close()


async def test_an_event_naming_an_access_change_skips_whoever_lost_access(topic: str) -> None:
    check = _Check()
    hub = _hub(check)
    (gone, gone_send), (named, named_send), (other, other_send) = [
        await _socket(hub, topic) for _ in range(3)
    ]
    check.allowed = {named.user_id, other.user_id}
    message = {"event": "member_changed", ACCESS_CHANGED_KEY: [gone.user_id, named.user_id]}
    event_bus.publish(topic, message)
    assert await _next(gone_send) == {"topic": topic, "error": "revoked"}
    await _nothing_arrives(gone_send)
    for send in (named_send, other_send):
        assert (await _next(send))["data"] == {"event": "member_changed"}
    named.close()
    other.close()


async def test_a_crash_in_one_run_is_logged_and_the_hub_keeps_working(
    topic: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = _Log()
    monkeypatch.setattr(ws_revocation, "logger", log)
    check = _Check()
    hub = _hub(check)
    subs, send = await _socket(hub, topic)
    real_revoke = subs.revoke
    crashes = [RuntimeError("socket gone")]

    def _revoke(t: str) -> None:
        if crashes:
            raise crashes.pop()
        real_revoke(t)

    monkeypatch.setattr(subs, "revoke", _revoke)
    check.allowed = set()
    event_bus.publish(_control(topic), {"user_ids": None})
    await _until(lambda: "ws_recheck_crashed" in log.events)
    event_bus.publish(_control(topic), {"user_ids": None})
    assert await _next(send) == {"topic": topic, "error": "revoked"}
