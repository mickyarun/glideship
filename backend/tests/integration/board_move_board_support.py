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

"""Helpers for moving cards between boards: two boards, labels, the move call, live events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from httpx import AsyncClient, Response

from app.services import event_bus
from tests.integration.board_api_support import BOARDS, Person, make_board, ok, person
from tests.integration.scan_features_bugs_support import Factory, new_org


@dataclass(frozen=True)
class TwoBoards:
    """A pm who administers an ops board (``source``) and a blank one (``target``)."""

    pm: Person
    source: dict[str, Any]
    target: dict[str, Any]

    @property
    def src(self) -> str:
        """The source board's key."""
        return str(self.source["board"]["key"])

    @property
    def dst(self) -> str:
        """The target board's key."""
        return str(self.target["board"]["key"])


async def two_boards(client: AsyncClient, factory: Factory, **target: Any) -> TwoBoards:
    """Both boards in a new org, made by one pm."""
    org = await new_org(factory)
    pm = await person(factory, org, "pm")
    source = await make_board(client, pm)
    return TwoBoards(pm, source, await make_board(client, pm, template="blank", **target))


async def label(client: AsyncClient, who: Person, key: str, name: str) -> str:
    """A new label on the board; its id."""
    body = {"name": name, "color": "red"}
    made = ok(await client.post(f"{BOARDS}/{key}/labels", json=body, headers=who.headers), 201)
    return str(made["id"])


async def move_board(
    client: AsyncClient, who: Person, key: str, card: dict[str, Any], target: str, **extra: Any
) -> Response:
    """POST …/move-board for the card; the raw response."""
    url = f"{BOARDS}/{key}/cards/{card['number']}/move-board"
    return await client.post(url, json={"target_board_key": target, **extra}, headers=who.headers)


def heard(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    """Every board-topic message published while the test runs."""
    sent: list[tuple[str, dict[str, Any]]] = []
    publish = event_bus.publish

    def _publish(topic: str, data: dict[str, Any]) -> None:
        if topic.startswith("board:"):
            sent.append((topic, data))
        publish(topic, data)

    monkeypatch.setattr(event_bus, "publish", _publish)
    return sent
