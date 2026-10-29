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

"""A socket drops a board subscription once a re-check says access is gone."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest

from app.api.v1.ws_subscriptions import ConnectionSubscriptions
from app.services import event_bus
from app.services.ws_topic_policy import Subscriber, access_topic

WHO = Subscriber(user_id=str(uuid.uuid4()), org_id=str(uuid.uuid4()), has_engineering=False)


class _Gate:
    """A scope check whose answer the test flips, counting its calls."""

    def __init__(self) -> None:
        self.allowed = True
        self.calls = 0

    async def __call__(self, topic: str, who: Subscriber) -> bool:
        self.calls += 1
        return self.allowed


async def _next(queue: asyncio.Queue[dict[str, Any]]) -> dict[str, Any]:
    return await asyncio.wait_for(queue.get(), timeout=1)


async def _settle() -> None:
    for _ in range(5):
        await asyncio.sleep(0)


@pytest.fixture
def board_topic() -> str:
    return f"board:{uuid.uuid4()}"


async def test_events_are_forwarded_until_a_recheck_fails(board_topic: str) -> None:
    send: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    gate = _Gate()
    subs = ConnectionSubscriptions(WHO, send, gate)
    subs.add(board_topic)
    await _settle()
    event_bus.publish(board_topic, {"event": "card_created"})
    assert (await _next(send))["data"] == {"event": "card_created"}

    gate.allowed = False
    control = access_topic(board_topic)
    assert control is not None
    event_bus.publish(control, {"user_ids": [WHO.user_id]})
    assert await _next(send) == {"topic": board_topic, "error": "revoked"}
    assert board_topic not in subs.topics

    event_bus.publish(board_topic, {"event": "card_updated"})
    await _settle()
    assert send.empty()
    subs.close()


async def test_a_recheck_for_someone_else_or_one_that_passes_keeps_it(board_topic: str) -> None:
    send: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    gate = _Gate()
    subs = ConnectionSubscriptions(WHO, send, gate)
    subs.add(board_topic)
    await _settle()
    control = access_topic(board_topic)
    assert control is not None

    gate.allowed = False
    event_bus.publish(control, {"user_ids": [str(uuid.uuid4())]})
    await _settle()
    assert gate.calls == 0 and board_topic in subs.topics

    gate.allowed = True
    event_bus.publish(control, {"user_ids": None})
    await _settle()
    assert gate.calls == 1 and board_topic in subs.topics
    assert send.empty()
    subs.close()


async def test_close_unsubscribes_from_the_bus(board_topic: str) -> None:
    subs = ConnectionSubscriptions(WHO, asyncio.Queue(), _Gate())
    subs.add(board_topic)
    subs.add(f"notifications:{WHO.user_id}")
    control = access_topic(board_topic)
    assert control is not None
    assert board_topic in event_bus._subscribers and control in event_bus._subscribers
    subs.close()
    assert board_topic not in event_bus._subscribers
    assert control not in event_bus._subscribers
    assert subs.topics == frozenset()


def test_only_revocable_scopes_have_a_control_topic() -> None:
    assert access_topic("board:abc") == "access:board:abc"
    assert access_topic(f"notifications:{WHO.user_id}") is None
    assert access_topic("access:board:abc") is None


async def test_a_recheck_that_errors_fails_closed(board_topic: str) -> None:
    async def _broken(topic: str, who: Subscriber) -> bool:
        raise RuntimeError("database unavailable")

    send: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    subs = ConnectionSubscriptions(WHO, send, _broken)
    subs.add(board_topic)
    await _settle()
    control = access_topic(board_topic)
    assert control is not None
    event_bus.publish(control, {"user_ids": None})
    assert await _next(send) == {"topic": board_topic, "error": "revoked"}
    assert subs.topics == frozenset()
