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

"""After a handover lands: timeline order, the estimate, the design hint and a failed start."""

from __future__ import annotations

import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.models.bud import BUDStatus
from app.repositories.bud_timeline import BUDTimelineRepository
from app.services.bud_metrics_phases import _phase_windows_from_timeline
from tests.integration.board_api_support import ok
from tests.integration.board_handover_support import card, desk, hand_over, stubbed
from tests.integration.board_notify_support import fake_slack, notes
from tests.integration.bud_lifecycle_reads import load_bud
from tests.integration.bud_lifecycle_support import (
    app_database_blocked as app_database_blocked,
)
from tests.integration.bud_lifecycle_support import stub_externals
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration

ESTIMATE = "app.services.bud_estimate_after_commit.schedule"


@pytest.fixture(autouse=True)
def _slack(monkeypatch: pytest.MonkeyPatch, pg_session_factory: Factory) -> None:
    fake_slack(monkeypatch, pg_session_factory)


async def test_landing_steps_read_in_order_and_the_target_gets_the_time(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """Database-clock stamps: created, then bud→design, then design→tech_arch."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="Compare plans")
    with stubbed():
        made = ok(await hand_over(client, d.pm, url, target_status="tech_arch"), 201)
    bud_id = uuid.UUID(made["handover"]["bud_id"])
    bud = await load_bud(pg_session_factory, bud_id)

    async with pg_session_factory() as db:
        events = await BUDTimelineRepository(db, org_id=d.org).list_for_bud(bud_id)
    changes = [e for e in events if e.event_type == "status_change"]
    assert [(e.detail or {})["to"] for e in changes] == ["design", "tech_arch"]
    stamps = [e.created_at for e in changes]
    assert bud.created_at < stamps[0] < stamps[1]
    kinds = [e.event_type for e in events]
    assert kinds.index("handed_over_from_board") < kinds.index("status_change")

    closed = stamps[1] + timedelta(days=3)
    windows = _phase_windows_from_timeline(
        [((e.detail or {})["to"], e.created_at) for e in changes], bud.created_at, closed
    )
    assert windows["design"] == (stamps[0], stamps[1])
    assert windows["tech_arch"] == (stamps[1], closed)
    lengths = {phase: end - start for phase, (start, end) in windows.items()}
    assert max(lengths, key=lambda phase: lengths[phase]) == "tech_arch"


@pytest.mark.parametrize(("target", "estimated"), [("bud", False), ("design", True)])
async def test_a_bud_landed_past_bud_is_estimated(
    client: AsyncClient, pg_session_factory: Factory, target: str, estimated: bool
) -> None:
    """The estimate a finished PRD would trigger, queued for after the commit."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="x")
    with stubbed(), patch(ESTIMATE) as schedule:
        made = ok(await hand_over(client, d.pm, url, target_status=target), 201)
    assert schedule.called is estimated
    if estimated:
        kwargs = schedule.call_args.kwargs
        assert kwargs["bud_id"] == uuid.UUID(made["handover"]["bud_id"])
        assert kwargs["trigger"] == "handover_landed"


@pytest.mark.parametrize(("phase_on", "hint"), [(True, True), (False, False)])
async def test_landing_at_design_says_whether_to_generate(
    client: AsyncClient, pg_session_factory: Factory, phase_on: bool, hint: bool
) -> None:
    """``design_available`` as the BUD page's header, through the real agent trigger."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="x")
    with stub_externals():
        made = ok(
            await hand_over(
                client,
                d.pm,
                url,
                target_status="design",
                auto_generate_phases={"design": phase_on},
            ),
            201,
        )
    assert made["design_available"] is hint
    assert made["handover"]["stage_start_failed"] is False


async def test_a_failed_start_leaves_the_bud_assigned_and_can_be_retried(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """Owner assigned and told in the transaction; the key again, or retry-start, restarts it."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="x")
    key = uuid.uuid4()
    body = {"target_status": "design", "auto_generate_phases": {"design": True}}
    with stubbed() as spawn:
        spawn.side_effect = RuntimeError("queue full")
        failed = ok(await hand_over(client, d.pm, url, key=key, **body), 201)
        assert failed["handover"]["stage_start_failed"] is True
        bud = await load_bud(pg_session_factory, uuid.UUID(failed["handover"]["bud_id"]))
        assert (bud.status, bud.assignee_id) == (BUDStatus.DESIGN, d.designer.id)
        assert [n.type for n in await notes(pg_session_factory, d.designer.id)] == [
            "board_handover"
        ]
        listed = ok(await client.get(f"{url}/handovers", headers=d.pm.headers))
        assert [h["stage_start_failed"] for h in listed["items"]] == [True]

        spawn.side_effect = None
        replay = ok(await hand_over(client, d.pm, url, key=key, **body), 201)
    assert spawn.await_count == 2
    assert replay["handover"]["id"] == failed["handover"]["id"]
    assert replay["handover"]["stage_start_failed"] is False


async def test_retry_start_runs_the_stage_once(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """``POST .../retry-start`` after a failure; a second retry is 409 HANDOVER_STAGE_STARTED."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="x")
    with stubbed() as spawn:
        spawn.side_effect = RuntimeError("queue full")
        made = ok(
            await hand_over(
                client, d.pm, url, target_status="design", auto_generate_phases={"design": True}
            ),
            201,
        )
        spawn.side_effect = None
        retry_url = f"{url}/handovers/{made['handover']['id']}/retry-start"
        retried = ok(await client.post(retry_url, headers=d.pm.headers))
        again = await client.post(retry_url, headers=d.pm.headers)
    assert spawn.await_count == 2
    assert retried["handover"]["stage_start_failed"] is False
    assert (again.status_code, again.json()["code"]) == (409, "HANDOVER_STAGE_STARTED")
    # The card is unchanged by a retry.
    assert retried["card"]["id"] == made["card"]["id"]
