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


"""Board work in the Garden: ``board_activity:<org_id>`` after a card is done, handed over
or delivered, naming the card only when its board is visible to the whole org."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from app.models.bud import BUDStatus
from app.services import event_bus
from tests.integration.board_api_support import (
    BOARDS,
    make_board,
    make_card,
    ok,
    person,
    stage_id,
)
from tests.integration.board_handover_return_support import BUDS, bud_of, handed, set_status
from tests.integration.board_handover_support import card, desk, stubbed
from tests.integration.board_notify_support import fake_slack
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration

Heard = list[tuple[str, dict[str, Any]]]


@pytest.fixture
def garden(monkeypatch: pytest.MonkeyPatch, pg_session_factory: Factory) -> Heard:
    """Every ``board_activity`` message published while the test runs."""
    fake_slack(monkeypatch, pg_session_factory)
    heard: Heard = []
    publish = event_bus.publish

    def _publish(topic: str, data: dict[str, Any]) -> None:
        if topic.startswith("board_activity:"):
            heard.append((topic, data))
        publish(topic, data)

    monkeypatch.setattr(event_bus, "publish", _publish)
    return heard


@pytest.mark.parametrize("visibility", ["org", "members"])
async def test_a_card_reaching_done_is_heard_once(
    client: AsyncClient, pg_session_factory: Factory, garden: Heard, visibility: str
) -> None:
    org = await new_org(pg_session_factory)
    pm = await person(pg_session_factory, org, "pm")
    board = await make_board(client, pm, visibility=visibility)
    key = board["board"]["key"]
    made = await make_card(client, pm, key, "Secret launch")
    url = f"{BOARDS}/{key}/cards/{made['number']}/move"

    for stage in ("In progress", "Done", "Backlog"):
        ok(await client.post(url, json={"stage_id": stage_id(board, stage)}, headers=pm.headers))

    expected: dict[str, Any] = {"kind": "card_done", "actor_id": str(pm.id)}
    if visibility == "org":
        expected |= {"board_key": key, "card_key": made["key"]}
    assert garden == [(f"board_activity:{org}", expected)]
    assert "Secret launch" not in str(garden)


async def test_a_handover_and_its_delivery_are_heard(
    client: AsyncClient, pg_session_factory: Factory, garden: Heard
) -> None:
    d = await desk(client, pg_session_factory)
    ok(
        await client.patch(
            f"{BOARDS}/{d.key}", json={"visibility": "members"}, headers=d.pm.headers
        )
    )
    url = await card(client, d, description_md="x")
    bud_id = bud_of(await handed(client, d.pm, url))
    await set_status(pg_session_factory, bud_id, BUDStatus.UAT)
    with stubbed():
        patch = await client.patch(
            f"{BUDS}/{bud_id}", json={"status": "prod"}, headers=d.pm.headers
        )
    ok(patch)

    kinds = [data for _topic, data in garden]
    assert kinds == [
        {"kind": "handover", "actor_id": str(d.pm.id)},
        {"kind": "bud_delivered", "actor_id": str(d.pm.id)},
    ]
    assert {topic for topic, _ in garden} == {f"board_activity:{d.org}"}
