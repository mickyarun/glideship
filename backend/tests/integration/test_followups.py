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

"""The daily follow-ups DM: what it lists, for whom, once per person per local day."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.models.bud import BUDStatus
from app.models.digest_claim import DigestClaimStatus
from app.services.followups import scheduler
from tests.integration.board_api_support import card_team, ok, org_of
from tests.integration.board_notify_support import link_slack
from tests.integration.followups_support import (
    Dms,
    capture_dms,
    due_card,
    followup_claims,
    opt_in,
    sections,
    target_bud,
)
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration

# Wednesday 13 March 2030, 09:00 in London (GMT, so UTC too).
AT = datetime(2030, 3, 13, 9, 0, tzinfo=UTC)


@pytest.fixture
def dms(monkeypatch: pytest.MonkeyPatch, pg_session_factory: Factory) -> Dms:
    return capture_dms(monkeypatch, pg_session_factory)


async def test_lists_overdue_today_and_coming_up_cards_and_bud_targets(
    client: AsyncClient, pg_session_factory: Factory, dms: Dms
) -> None:
    team = await card_team(client, pg_session_factory)
    org = await org_of(pg_session_factory, team.admin)
    ids = await link_slack(pg_session_factory, org, team.editor.id, team.viewer.id)
    ed, key = team.editor, team.key
    await opt_in(pg_session_factory, org, ed.id)
    late = await due_card(client, team.admin, key, "Partner link flow", "2030-03-11T08:00:00Z", ed)
    await due_card(client, team.admin, key, "Pricing page", "2030-03-13T15:00:00Z", ed)
    await due_card(client, team.admin, key, "Launch post", "2030-03-15T10:00:00Z", ed)
    await due_card(client, team.admin, key, "Next week", "2030-03-20T10:00:00Z", ed)
    comment = {"body": "Sent them a detailed email with examples"}
    url = f"/api/v1/boards/{key}/cards/{late['number']}/comments"
    ok(await client.post(url, json=comment, headers=team.viewer.headers), 201)
    await target_bud(pg_session_factory, org, 41, ed.id, datetime(2030, 3, 12, tzinfo=UTC))
    closed = datetime(2030, 3, 12, tzinfo=UTC)
    await target_bud(pg_session_factory, org, 42, ed.id, closed, BUDStatus.CLOSED)

    await scheduler.tick_once(AT)

    (blocks,) = dms.to(ids[ed.id])
    texts = sections(blocks)
    assert "|BUD-041 Feature 41>" in texts[1] and "_Development_" in texts[1]
    assert "Partner link flow" in texts[0] and "*overdue by 2d*" in texts[0]
    assert "Target Tue 12 Mar" in texts[1]
    assert "Pricing page" in texts[2] and "today" in texts[2]
    assert "Launch post" in texts[3] and "in 2d" in texts[3]
    assert len(texts) == 4
    context = blocks[3]["elements"][0]["text"]
    assert "Last comment" in context and "detailed email" in context
    # The viewer didn't opt in; nothing is sent to them.
    assert dms.to(ids[team.viewer.id]) == []


async def test_one_dm_per_person_per_day_across_ticks_and_workers(
    client: AsyncClient, pg_session_factory: Factory, dms: Dms
) -> None:
    team = await card_team(client, pg_session_factory)
    org = await org_of(pg_session_factory, team.admin)
    ids = await link_slack(pg_session_factory, org, team.editor.id)
    await opt_in(pg_session_factory, org, team.editor.id)
    await due_card(client, team.admin, team.key, "Thu", "2030-03-14T12:00:00Z", team.editor)
    day = datetime(2030, 3, 14, 9, 0, tzinfo=UTC)

    # Two workers tick at the same instant, then a later tick and a restart.
    await asyncio.gather(scheduler.tick_once(day), scheduler.tick_once(day))
    await scheduler.tick_once(day.replace(minute=30))
    await scheduler.tick_once(day)

    assert len(dms.to(ids[team.editor.id])) == 1
    (claim,) = await followup_claims(pg_session_factory, org)
    assert claim.status is DigestClaimStatus.SENT and claim.attempts == 0


async def test_nothing_due_sends_nothing_and_is_recorded(
    client: AsyncClient, pg_session_factory: Factory, dms: Dms
) -> None:
    team = await card_team(client, pg_session_factory)
    org = await org_of(pg_session_factory, team.admin)
    ids = await link_slack(pg_session_factory, org, team.editor.id)
    await opt_in(pg_session_factory, org, team.editor.id)
    friday = datetime(2030, 3, 15, 9, 0, tzinfo=UTC)

    await scheduler.tick_once(friday)

    assert dms.to(ids[team.editor.id]) == []
    (claim,) = await followup_claims(pg_session_factory, org)
    assert claim.status is DigestClaimStatus.SKIPPED and claim.error == "nothing_due"


async def test_a_failed_send_is_retried_by_a_later_tick(
    client: AsyncClient, pg_session_factory: Factory, dms: Dms
) -> None:
    team = await card_team(client, pg_session_factory)
    org = await org_of(pg_session_factory, team.admin)
    ids = await link_slack(pg_session_factory, org, team.editor.id)
    await opt_in(pg_session_factory, org, team.editor.id)
    monday = datetime(2030, 3, 18, 9, 0, tzinfo=UTC)
    await due_card(client, team.admin, team.key, "Mon", "2030-03-18T12:00:00Z", team.editor)

    dms.fail = True
    await scheduler.tick_once(monday)
    (claim,) = await followup_claims(pg_session_factory, org)
    assert claim.status is DigestClaimStatus.FAILED

    dms.fail = False
    await scheduler.tick_once(monday.replace(minute=5))
    assert len(dms.to(ids[team.editor.id])) == 1
    (claim,) = await followup_claims(pg_session_factory, org)
    assert claim.status is DigestClaimStatus.SENT and claim.attempts == 1
