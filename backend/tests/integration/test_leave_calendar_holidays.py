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

"""Public holidays as Out of office on people's Google Calendars, with Google faked.

Each person has their own fake calendar, holding events by id with the tag
and end time Google would keep, plus one event they made themselves.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

import pytest
from sqlalchemy import delete

from app.models.leave_request import LeaveKind
from app.models.policy_holiday import PolicyHoliday
from app.repositories.leave_request import LeaveRequestRepository
from app.repositories.user import UserRepository
from app.schemas.leave_calendar_sync import CalendarSyncOptions
from app.services.google.calendar_api import TAG, Event
from app.services.google.service_account import ServiceAccountKey
from app.services.leave.calendar_sync import holiday_sync, sync
from app.services.leave.calendar_sync.events import HOLIDAY_TAG
from app.services.leave.calendar_sync.settings import CalendarSync
from app.services.leave.policies import ensure_default_policy
from tests.integration.leave_edge_support import (
    add_holiday,
    add_policy,
    deactivate,
    freeze_today,
    place,
)
from tests.integration.leave_support import Factory, add_request, setup_org

pytestmark = pytest.mark.integration
KEY = ServiceAccountKey("bot@proj.iam.gserviceaccount.com", "-----BEGIN PRIVATE KEY-----")
OWN_EVENT = "dentist"
TODAY = date(2030, 6, 10)  # Mon
FEST = date(2030, 6, 12)  # Wed
FOREVER = datetime(9999, 1, 1, tzinfo=UTC)


class FakeCalendars:
    """Per person: event id → (tag, end). The token is the person's email."""

    def __init__(self) -> None:
        self.calendars: dict[str, dict[str, tuple[str | None, datetime]]] = {}
        self.enabled = True

    def of(self, email: str) -> dict[str, tuple[str | None, datetime]]:
        return self.calendars.setdefault(email, {OWN_EVENT: (None, FOREVER)})

    async def access_token(self, _key: ServiceAccountKey, email: str, _scope: str) -> str:
        return email

    async def tagged_event_ids(
        self, token: str, tag: str, *, since: datetime | None = None
    ) -> set[str]:
        return {
            i
            for i, (t, end) in self.of(token).items()
            if t == tag and (since is None or end > since)
        }

    async def put_event(self, token: str, event_id: str, body: Event, *, exists: bool) -> None:
        assert exists == (event_id in self.of(token))
        end = body["end"].get("dateTime") or body["end"]["date"]
        self.of(token)[event_id] = (
            body["extendedProperties"]["private"][TAG],
            datetime.fromisoformat(end),
        )

    async def delete_event(self, token: str, event_id: str) -> None:
        del self.of(token)[event_id]

    def holidays_of(self, email: str) -> set[str]:
        return {i for i, (t, _end) in self.of(email).items() if t == HOLIDAY_TAG}


@pytest.fixture
def google(monkeypatch: pytest.MonkeyPatch, pg_session_factory: Factory) -> FakeCalendars:
    fake = FakeCalendars()
    for name in ("tagged_event_ids", "put_event", "delete_event"):
        monkeypatch.setattr(sync.calendar_api, name, getattr(fake, name))
    monkeypatch.setattr(sync, "access_token", fake.access_token)
    for module in (sync, holiday_sync):
        monkeypatch.setattr(module, "AsyncSessionLocal", pg_session_factory)

    async def settings(*_args: Any) -> CalendarSync:
        return CalendarSync(options=CalendarSyncOptions(enabled=fake.enabled), key=KEY)

    for module in (sync, holiday_sync):
        monkeypatch.setattr(module, "load_sync", settings)
    freeze_today(monkeypatch, TODAY)
    return fake


async def _emails(factory: Factory, *users: uuid.UUID) -> list[str]:
    async with factory() as db:
        rows = {u.id: u.email for u in await UserRepository(db).get_many_by_ids(list(users))}
    return [rows[u] for u in users]


async def _default_policy(factory: Factory, org: uuid.UUID) -> uuid.UUID:
    async with factory() as db:
        return (await ensure_default_policy(db, org)).id


async def test_a_holiday_goes_on_everyone_on_that_policy_and_comes_off_when_deleted(
    pg_session_factory: Factory, google: FakeCalendars
) -> None:
    org, (emp, peer, away), _ = await setup_org(pg_session_factory, "Emp", "Peer", "Away")
    other_policy, _ = await add_policy(pg_session_factory, org, "Elsewhere")
    await place(pg_session_factory, org, away, other_policy)
    policy = await _default_policy(pg_session_factory, org)
    await add_holiday(pg_session_factory, org, policy, FEST, "Fest")
    emp_mail, peer_mail, away_mail = await _emails(pg_session_factory, emp, peer, away)

    await holiday_sync.sync_holidays(org)
    assert google.holidays_of(emp_mail) == {"bohol20300612"}
    assert google.holidays_of(peer_mail) == {"bohol20300612"}
    assert google.holidays_of(away_mail) == set()

    async with pg_session_factory() as db:
        await db.execute(delete(PolicyHoliday).where(PolicyHoliday.policy_id == policy))
        await db.commit()
    await holiday_sync.sync_holidays(org, policy_id=policy)
    assert google.holidays_of(emp_mail) == set()
    assert google.of(emp_mail)[OWN_EVENT][0] is None  # their own event is untouched


async def test_past_holidays_stay_and_switching_sync_off_clears_the_rest(
    pg_session_factory: Factory, google: FakeCalendars
) -> None:
    org, (emp,), _ = await setup_org(pg_session_factory, "Emp")
    policy = await _default_policy(pg_session_factory, org)
    await add_holiday(pg_session_factory, org, policy, FEST, "Fest")
    (mail,) = await _emails(pg_session_factory, emp)
    google.of(mail)["bohol20300101"] = (HOLIDAY_TAG, datetime(2030, 1, 2, tzinfo=UTC))

    await holiday_sync.sync_holidays(org)
    assert google.holidays_of(mail) == {"bohol20300101", "bohol20300612"}

    google.enabled = False
    await holiday_sync.sync_holidays(org)
    assert google.holidays_of(mail) == {"bohol20300101"}


async def test_someone_who_leaves_has_their_holidays_taken_off_once(
    pg_session_factory: Factory, google: FakeCalendars
) -> None:
    org, (emp, gone), _ = await setup_org(pg_session_factory, "Emp", "Gone")
    policy = await _default_policy(pg_session_factory, org)
    await add_holiday(pg_session_factory, org, policy, FEST, "Fest")
    emp_mail, gone_mail = await _emails(pg_session_factory, emp, gone)
    await holiday_sync.sync_holidays(org)
    assert google.holidays_of(gone_mail) == {"bohol20300612"}

    await deactivate(pg_session_factory, gone)
    await holiday_sync.sync_holidays(org, user_ids=[gone])
    assert google.holidays_of(gone_mail) == set()
    # Everyone-syncs don't open a leaver's calendar again.
    del google.calendars[gone_mail]
    await holiday_sync.sync_holidays(org)
    assert gone_mail not in google.calendars
    assert google.holidays_of(emp_mail) == {"bohol20300612"}


async def test_a_holiday_on_a_day_off_is_not_put_on_the_calendar(
    pg_session_factory: Factory, google: FakeCalendars
) -> None:
    org, (emp,), _ = await setup_org(pg_session_factory, "Emp")
    policy = await _default_policy(pg_session_factory, org)
    await add_holiday(pg_session_factory, org, policy, date(2030, 6, 15), "Saturday fest")
    (mail,) = await _emails(pg_session_factory, emp)
    await holiday_sync.sync_holidays(org)
    assert google.holidays_of(mail) == set()


async def test_a_new_holiday_inside_a_wfh_takes_that_days_home_entry_away(
    pg_session_factory: Factory, google: FakeCalendars
) -> None:
    org, (emp,), _ = await setup_org(pg_session_factory, "Emp")
    policy = await _default_policy(pg_session_factory, org)
    await add_request(
        pg_session_factory, org, emp, TODAY, date(2030, 6, 14), "5", kind=LeaveKind.WFH
    )
    (mail,) = await _emails(pg_session_factory, emp)
    async with pg_session_factory() as db:
        (wfh,) = await LeaveRequestRepository(db, org_id=org).active_between([emp], TODAY, TODAY)
    await sync.sync_request(org, wfh.id)
    home = {i for i, (t, _e) in google.of(mail).items() if t == wfh.id.hex}
    assert len(home) == 5

    await add_holiday(pg_session_factory, org, policy, FEST, "Fest")
    await holiday_sync.after_holiday_change(org, policy, FEST)
    home = {i for i, (t, _e) in google.of(mail).items() if t == wfh.id.hex}
    assert f"bo{wfh.id.hex}d20300612" not in home and len(home) == 4
    assert google.holidays_of(mail) == {"bohol20300612"}
