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

"""Who the follow-ups skip: other timezones, leave, holidays; and the card reminder hand-off."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.leave_request import HalfDay, LeaveKind, LeaveRequest
from app.models.organization import Organization
from app.repositories.board_due import DueOrg
from app.services.boards import due_reminders
from app.services.followups import scheduler
from tests.integration.board_api_support import card_team, org_of
from tests.integration.board_notify_support import link_slack
from tests.integration.followups_support import (
    Dms,
    capture_dms,
    due_card,
    followup_claims,
    mandatory_holiday,
    opt_in,
)
from tests.integration.leave_support import add_request
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration

# The card reminder fires at 08:00 Kolkata time (02:30 UTC).
REMINDER = {"leave_digest": {"timezone": "Asia/Kolkata"}, "boards": {"due_reminder_time": "08:00"}}


async def _card_reminder_org(factory: Factory, org: uuid.UUID) -> DueOrg:
    async with factory() as db:
        organization = await db.get(Organization, org)
        assert organization is not None
        organization.config = REMINDER
        await db.commit()
    return DueOrg(org_id=org, config=REMINDER, policy_timezone=None)


async def _half_day(factory: Factory, user_id: uuid.UUID, day: date) -> None:
    async with factory() as db:
        request = await db.scalar(
            select(LeaveRequest).where(
                LeaveRequest.user_id == user_id, LeaveRequest.start_date == day
            )
        )
        assert request is not None
        request.half_day = HalfDay.FIRST_HALF
        await db.commit()


@pytest.fixture
def dms(monkeypatch: pytest.MonkeyPatch, pg_session_factory: Factory) -> Dms:
    monkeypatch.setattr(due_reminders, "AsyncSessionLocal", pg_session_factory)
    return capture_dms(monkeypatch, pg_session_factory)


async def test_each_person_gets_it_at_their_own_local_time(
    client: AsyncClient, pg_session_factory: Factory, dms: Dms
) -> None:
    team = await card_team(client, pg_session_factory)
    org = await org_of(pg_session_factory, team.admin)
    ed, vw = team.editor, team.viewer
    ids = await link_slack(pg_session_factory, org, ed.id, vw.id)
    await opt_in(pg_session_factory, org, ed.id, at=time(9, 0), zone="Asia/Kolkata")
    await opt_in(pg_session_factory, org, vw.id, at=time(9, 0), zone="Europe/London")
    await due_card(client, team.admin, team.key, "Shared", "2030-03-19T20:00:00Z", ed, vw)

    # Tuesday 19 March, 03:30 UTC: 09:00 in Kolkata, 03:30 in London.
    await scheduler.tick_once(datetime(2030, 3, 19, 3, 30, tzinfo=UTC))
    assert len(dms.to(ids[ed.id])) == 1 and dms.to(ids[vw.id]) == []

    await scheduler.tick_once(datetime(2030, 3, 19, 9, 0, tzinfo=UTC))
    assert len(dms.to(ids[vw.id])) == 1 and len(dms.to(ids[ed.id])) == 1


async def test_people_on_leave_or_a_holiday_are_skipped_but_wfh_is_not(
    client: AsyncClient, pg_session_factory: Factory, dms: Dms
) -> None:
    team = await card_team(client, pg_session_factory)
    org = await org_of(pg_session_factory, team.admin)
    ed, vw, admin = team.editor, team.viewer, team.admin
    ids = await link_slack(pg_session_factory, org, ed.id, vw.id, admin.id)
    for who in (ed, vw, admin):
        await opt_in(pg_session_factory, org, who.id)
    await due_card(client, admin, team.key, "Everyone", "2030-03-20T12:00:00Z", ed, vw, admin)
    wednesday = date(2030, 3, 20)
    await add_request(pg_session_factory, org, ed.id, wednesday, wednesday, "1")
    await add_request(
        pg_session_factory, org, vw.id, wednesday, wednesday, "1", kind=LeaveKind.WFH
    )

    await scheduler.tick_once(datetime(2030, 3, 20, 9, 0, tzinfo=UTC))

    assert dms.to(ids[ed.id]) == []
    assert len(dms.to(ids[vw.id])) == 1 and len(dms.to(ids[admin.id])) == 1
    away = [c for c in await followup_claims(pg_session_factory, org) if c.user_id == ed.id]
    assert [c.error for c in away] == ["away"]

    # A half day off still gets it; a mandatory holiday skips everyone.
    thursday = date(2030, 3, 21)
    await add_request(pg_session_factory, org, vw.id, thursday, thursday, "0.5")
    await _half_day(pg_session_factory, vw.id, thursday)
    await scheduler.tick_once(datetime(2030, 3, 21, 9, 0, tzinfo=UTC))
    assert len(dms.to(ids[vw.id])) == 2
    await mandatory_holiday(pg_session_factory, org, date(2030, 3, 22))
    await scheduler.tick_once(datetime(2030, 3, 22, 9, 0, tzinfo=UTC))
    assert len(dms.to(ids[vw.id])) == 2 and len(dms.to(ids[admin.id])) == 2


async def test_opted_in_people_get_cards_here_not_in_the_card_reminder(
    client: AsyncClient, pg_session_factory: Factory, dms: Dms
) -> None:
    team = await card_team(client, pg_session_factory)
    org = await org_of(pg_session_factory, team.admin)
    config = await _card_reminder_org(pg_session_factory, org)
    ed, vw = team.editor, team.viewer
    ids = await link_slack(pg_session_factory, org, ed.id, vw.id)
    await opt_in(pg_session_factory, org, ed.id)
    await due_card(client, team.admin, team.key, "Overdue", "2030-03-01T10:00:00Z", ed, vw)

    # Monday 08:30 in Kolkata: follow-ups go out today, so no card DM for the editor.
    await due_reminders.org_pass(config, datetime(2030, 3, 4, 3, 0, tzinfo=UTC))
    assert dms.to(ids[ed.id]) == [] and len(dms.to(ids[vw.id])) == 1

    # Saturday: weekdays-only follow-ups don't go out, so the card DM does.
    await due_reminders.org_pass(config, datetime(2030, 3, 9, 3, 0, tzinfo=UTC))
    assert len(dms.to(ids[ed.id])) == 1

    # A weekday on leave: the follow-ups skip them, so the card DM goes as before.
    tuesday = date(2030, 3, 12)
    await add_request(pg_session_factory, org, ed.id, tuesday, tuesday, "1")
    await due_reminders.org_pass(config, datetime(2030, 3, 12, 3, 0, tzinfo=UTC))
    assert len(dms.to(ids[ed.id])) == 2
