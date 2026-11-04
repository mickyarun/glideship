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

"""Follow-ups respect access: BUDs need the engineering workspace, and on/off is per org."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time

import pytest
from httpx import AsyncClient

from app.models.user import OrgToUser, User
from app.repositories.followup_settings import followup_subscribers
from app.schemas.followups import FollowupSettingsUpdate
from app.services.followups import scheduler
from app.services.followups.settings import read_settings, save_settings
from tests.integration.board_api_support import card_team, org_of, person, put_role
from tests.integration.board_notify_support import link_slack
from tests.integration.followups_support import (
    Dms,
    capture_dms,
    due_card,
    save_schedule,
    sections,
    target_bud,
)
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration

CATEGORY = "daily_followups"
NINE = time(9, 0)

# Tuesday 26 March 2030, 09:00 in London (GMT).
AT = datetime(2030, 3, 26, 9, 0, tzinfo=UTC)


@pytest.fixture
def dms(monkeypatch: pytest.MonkeyPatch, pg_session_factory: Factory) -> Dms:
    return capture_dms(monkeypatch, pg_session_factory)


async def test_a_bud_is_left_out_for_someone_who_cannot_open_buds(
    client: AsyncClient, pg_session_factory: Factory, dms: Dms
) -> None:
    team = await card_team(client, pg_session_factory)
    org = await org_of(pg_session_factory, team.admin)
    seller = await person(pg_session_factory, org, "sales")
    await put_role(client, team.admin, team.key, seller.id, "editor")
    ids = await link_slack(pg_session_factory, org, seller.id)
    await save_schedule(pg_session_factory, org, seller.id)
    await due_card(client, team.admin, team.key, "Pricing deck", "2030-03-26T12:00:00Z", seller)
    await target_bud(pg_session_factory, org, 61, seller.id, datetime(2030, 3, 25, tzinfo=UTC))

    await scheduler.tick_once(AT)

    (blocks,) = dms.to(ids[seller.id])
    texts = sections(blocks)
    assert len(texts) == 1 and "Pricing deck" in texts[0]


async def test_turning_it_off_in_one_org_leaves_the_other_org_on(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    team = await card_team(client, pg_session_factory)
    first = await org_of(pg_session_factory, team.admin)
    second = await new_org(pg_session_factory)
    me = team.editor.id
    async with pg_session_factory() as db:
        db.add(OrgToUser(user_id=me, org_id=second))
        await db.commit()
    await link_slack(pg_session_factory, first, me)

    async def my_orgs() -> set[uuid.UUID]:
        async with pg_session_factory() as db:
            people = await followup_subscribers(db, CATEGORY, default_time=NINE)
        return {s.org_id for s in people if s.user_id == me}

    # Never touched: on in both orgs.
    assert await my_orgs() == {first, second}

    off = FollowupSettingsUpdate(enabled=False, send_time="09:00", timezone="Europe/London")
    async with pg_session_factory() as db:
        await save_settings(db, second, me, off)
        await db.commit()
        assert (await read_settings(db, first, me)).enabled is True
        assert (await read_settings(db, second, me)).enabled is False
    assert await my_orgs() == {first}

    async with pg_session_factory() as db:
        await save_settings(db, first, me, off)
        await db.commit()
    assert await my_orgs() == set()


async def test_an_old_account_wide_off_keeps_it_off_everywhere(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    team = await card_team(client, pg_session_factory)
    org = await org_of(pg_session_factory, team.admin)
    await link_slack(pg_session_factory, org, team.editor.id)
    async with pg_session_factory() as db:
        user = await db.get(User, team.editor.id)
        assert user is not None
        user.notification_prefs = {CATEGORY: False}
        await db.commit()
        people = await followup_subscribers(db, CATEGORY, default_time=NINE)
    assert team.editor.id not in {s.user_id for s in people}
