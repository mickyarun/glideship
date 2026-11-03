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

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.models.user import OrgToUser
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
    opt_in,
    sections,
    target_bud,
)
from tests.integration.scan_features_bugs_support import Factory, new_org

pytestmark = pytest.mark.integration

CATEGORY = "daily_followups"

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
    await opt_in(pg_session_factory, org, seller.id)
    await due_card(client, team.admin, team.key, "Pricing deck", "2030-03-26T12:00:00Z", seller)
    await target_bud(pg_session_factory, org, 61, seller.id, datetime(2030, 3, 25, tzinfo=UTC))

    await scheduler.tick_once(AT)

    (blocks,) = dms.to(ids[seller.id])
    texts = sections(blocks)
    assert len(texts) == 1 and "Pricing deck" in texts[0]


async def test_turning_it_on_in_one_org_leaves_the_other_org_as_it_was(
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
    on = FollowupSettingsUpdate(enabled=True, send_time="09:00", timezone="Europe/London")
    async with pg_session_factory() as db:
        await save_settings(db, second, me, on)
        await save_settings(db, second, me, on.model_copy(update={"enabled": False}))
        await save_settings(db, first, me, on)
        await db.commit()

    async with pg_session_factory() as db:
        assert (await read_settings(db, first, me)).enabled is True
        assert (await read_settings(db, second, me)).enabled is False
        orgs = [
            s.org_id for s in await followup_subscribers(db, "daily_followups") if s.user_id == me
        ]
    assert orgs == [first]

    # Off in the only org where it was on: off everywhere, and the prefs say so.
    async with pg_session_factory() as db:
        await save_settings(db, first, me, on.model_copy(update={"enabled": False}))
        await db.commit()
        assert [
            s for s in await followup_subscribers(db, "daily_followups") if s.user_id == me
        ] == []
