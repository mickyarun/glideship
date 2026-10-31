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

"""Handing a card over creates a BUD and lands it at bud, design or the tech plan."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.bud import BUDDocument, BUDStatus
from app.models.developer_xp import RewardEvent, RewardType
from app.services.sp_pm import award_pm_sp_on_close
from tests.integration.board_api_support import ok
from tests.integration.board_handover_support import (
    ALL_PHASES,
    card,
    card_stage,
    desk,
    first_editor,
    hand_over,
    spawned_stages,
    status_changes,
    stubbed,
)
from tests.integration.board_notify_support import fake_slack
from tests.integration.bud_lifecycle_reads import load_bud, timeline
from tests.integration.bud_lifecycle_support import (
    app_database_blocked as app_database_blocked,
)
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _slack(monkeypatch: pytest.MonkeyPatch, pg_session_factory: Factory) -> None:
    fake_slack(monkeypatch, pg_session_factory)


@pytest.mark.parametrize(
    ("target", "skipped"),
    [
        ("bud", []),
        ("design", [("bud", "design")]),
        ("tech_arch", [("bud", "design"), ("design", "tech_arch")]),
    ],
)
async def test_lands_at_the_target_and_runs_only_its_stage(
    client: AsyncClient, pg_session_factory: Factory, target: str, skipped: list[tuple[str, str]]
) -> None:
    """Skipped stages get ordinary status changes by the PM; only the target's agent runs."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="Customers compare plans side by side.")
    with stubbed() as spawn:
        body = ok(
            await hand_over(
                client, d.pm, url, target_status=target, auto_generate_phases=ALL_PHASES
            ),
            201,
        )

    handover = body["handover"]
    bud_id = uuid.UUID(handover["bud_id"])
    assert (handover["bud_status"], handover["target_status"]) == (target, target)
    assert handover["linked_existing"] is False and handover["status"] == "active"
    bud = await load_bud(pg_session_factory, bud_id)
    assert bud.status is BUDStatus(target)
    assert await status_changes(pg_session_factory, bud_id) == [
        (a, b, "handover", d.pm.id) for a, b in skipped
    ]
    assert spawned_stages(spawn) == [target]
    owners = {"bud": d.pm.id, "design": d.designer.id, "tech_arch": d.lead.id}
    assert bud.assignee_id == owners[target]
    [origin] = await timeline(pg_session_factory, bud_id, "handed_over_from_board")
    assert origin["card_id"] == body["card"]["id"]
    assert origin["card_key"] == body["card"]["key"]


async def test_the_handing_over_person_is_the_author_and_gets_the_pm_credit(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """Earliest version edited by the PM; sp_pm pays the PM for the move to design."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="Plans table")
    with stubbed():
        body = ok(await hand_over(client, d.pm, url, target_status="design"), 201)
    bud_id = uuid.UUID(body["handover"]["bud_id"])

    assert await first_editor(pg_session_factory, bud_id) == d.pm.id
    async with pg_session_factory() as db:
        bud = await db.get(BUDDocument, bud_id)
        assert bud is not None
        await award_pm_sp_on_close(db, d.org, bud)
        await db.commit()
        paid = await db.scalars(
            select(RewardEvent.user_id).where(
                RewardEvent.org_id == d.org,
                RewardEvent.type == RewardType.SP,
                RewardEvent.source == "sp_pm_requirement",
            )
        )
        assert list(paid) == [d.pm.id]


async def test_carries_the_card_over_and_moves_it_once(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """Title, priority, requirements; the card moves to Ready for dev on its first handover."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, "Compare plans", priority="P1", description_md="Side by side")
    with stubbed():
        first = ok(await hand_over(client, d.pm, url), 201)
        moved_to = await card_stage(pg_session_factory, first["card"]["id"])
        second = ok(await hand_over(client, d.pm, url), 201)

    bud = await load_bud(pg_session_factory, uuid.UUID(first["handover"]["bud_id"]))
    assert (bud.title, bud.priority) == ("Compare plans", "P1")
    assert bud.requirements_md is not None
    assert bud.requirements_md.startswith("Side by side\n\n## From the board")
    assert str(moved_to) == d.stage("Ready for dev") == first["card"]["stage_id"]
    assert second["handover"]["bud_id"] != first["handover"]["bud_id"]
    assert second["card"]["stage_id"] == d.stage("Ready for dev")
    listed = ok(await client.get(f"{url}/handovers", headers=d.pm.headers))
    assert [h["bud_id"] for h in listed["items"]] == [
        first["handover"]["bud_id"],
        second["handover"]["bud_id"],
    ]
    assert listed["can_hand_over"] is True


async def test_a_repeated_key_returns_the_first_handover(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """A double click or retry never makes a second BUD."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="x")
    key = uuid.uuid4()
    with stubbed():
        first = ok(await hand_over(client, d.pm, url, key=key), 201)
        again = ok(await hand_over(client, d.pm, url, key=key, target_status="design"), 201)
    assert again["handover"] == first["handover"]
    listed = ok(await client.get(f"{url}/handovers", headers=d.pm.headers))
    assert len(listed["items"]) == 1


async def test_the_first_handover_asks_before_completing_an_open_checklist(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """409 CHECKLIST_OPEN with nothing written; confirming moves it."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="x")
    ok(await client.post(f"{url}/checklist", json={"text": "Copy"}, headers=d.pm.headers), 201)
    with stubbed():
        refused = await hand_over(client, d.pm, url)
        assert refused.status_code == 409 and refused.json()["code"] == "CHECKLIST_OPEN"
        listed = ok(await client.get(f"{url}/handovers", headers=d.pm.headers))
        assert listed["items"] == []
        done = ok(await hand_over(client, d.pm, url, confirm_open_checklist=True), 201)
    assert done["card"]["stage_id"] == d.stage("Ready for dev")
