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

"""Every confirm's key replays it, a re-handover's preview says what it reopens, and races."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.agent_skill import AgentSkill, AgentType
from app.models.board_handover import BoardCardHandover
from app.models.bud import BUDDocument
from app.models.bud_stage_skill_override import BUDStageSkillOverride
from app.repositories.board_handover import BoardHandoverRepository
from tests.integration.board_api_support import ok, person, put_role
from tests.integration.board_handover_return_support import BUDS, bud_of, handed, send_back
from tests.integration.board_handover_support import card, desk, hand_over, preview, stubbed
from tests.integration.board_notify_support import fake_slack
from tests.integration.bud_lifecycle_support import (
    app_database_blocked as app_database_blocked,
)
from tests.integration.scan_features_bugs_support import Factory

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _slack(monkeypatch: pytest.MonkeyPatch, pg_session_factory: Factory) -> None:
    fake_slack(monkeypatch, pg_session_factory)


async def _buds(factory: Factory, org: uuid.UUID) -> int:
    async with factory() as db:
        return int(await db.scalar(select(func.count()).where(BUDDocument.org_id == org)) or 0)


async def test_a_key_from_before_a_send_back_still_replays(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """Hand over, send back, hand over again: both keys return their handover, no new BUD."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="x")
    first_key, second_key = uuid.uuid4(), uuid.uuid4()
    first = await handed(client, d.pm, url, key=first_key)
    ok(await send_back(client, d.pm, bud_of(first)))
    again = await handed(client, d.pm, url, key=second_key)
    count = await _buds(pg_session_factory, d.org)

    old = await handed(client, d.pm, url, key=first_key)
    new = await handed(client, d.pm, url, key=second_key)
    assert old["handover"]["id"] == new["handover"]["id"] == again["handover"]["id"]
    assert bud_of(old) == bud_of(first)
    assert await _buds(pg_session_factory, d.org) == count


async def test_another_person_replaying_a_key_gets_it_only_with_the_rights(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """An editor who may hand over gets the same handover; one who may not is 403; no new BUD."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="x")
    key = uuid.uuid4()
    first = await handed(client, d.pm, url, key=key)
    other_pm = await person(pg_session_factory, d.org, "pm")
    sales = await person(pg_session_factory, d.org, "sales")
    for who in (other_pm, sales):
        await put_role(client, d.pm, d.key, who.id, "editor")
    count = await _buds(pg_session_factory, d.org)

    with stubbed():
        theirs = ok(await hand_over(client, other_pm, url, key=key), 201)
        refused = await hand_over(client, sales, url, key=key)
    assert theirs["handover"]["id"] == first["handover"]["id"]
    assert refused.status_code == 403
    assert await _buds(pg_session_factory, d.org) == count


async def test_the_preview_says_which_bud_a_create_reopens(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """Null before; after a send-back, the BUD's key and that it's discarded."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="x")
    with stubbed():
        before = ok(await preview(client, d.pm, url))
    made = await handed(client, d.pm, url)
    ok(await send_back(client, d.pm, bud_of(made)))
    with stubbed():
        after = ok(await preview(client, d.pm, url))
    assert before["reopens"] is None
    assert after["reopens"] == {"bud_key": made["handover"]["bud_key"], "status": "discarded"}


async def test_handing_over_again_replaces_the_stage_skill_picks(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """Picks from the first handover don't survive a second one that names none."""
    d = await desk(client, pg_session_factory)
    async with pg_session_factory() as db:
        skill = AgentSkill(
            org_id=d.org, skill_slug="designer", agent_type=AgentType.DESIGN, name="D", prompt="p"
        )
        db.add(skill)
        await db.commit()
        skill_id = skill.id
    url = await card(client, d, description_md="x")
    made = await handed(client, d.pm, url, stage_skill_overrides={"design": str(skill_id)})
    assert await _picks(pg_session_factory, bud_of(made)) == 1
    ok(await send_back(client, d.pm, bud_of(made)))
    again = await handed(client, d.pm, url)
    assert bud_of(again) == bud_of(made)
    assert await _picks(pg_session_factory, bud_of(made)) == 0


async def _picks(factory: Factory, bud_id: uuid.UUID) -> int:
    async with factory() as db:
        stmt = select(func.count()).where(BUDStageSkillOverride.bud_id == bud_id)
        return int(await db.scalar(stmt) or 0)


async def test_a_sent_back_bud_restored_meanwhile_is_409(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """Read as sent back, restored before the locks: 409 BUD_NOT_RETURNED, nothing written."""
    d = await desk(client, pg_session_factory)
    url = await card(client, d, description_md="x")
    made = await handed(client, d.pm, url)
    ok(await send_back(client, d.pm, bud_of(made)))
    async with pg_session_factory() as db:
        row_id = await db.scalar(
            select(BoardCardHandover.id).where(BoardCardHandover.bud_id == bud_of(made))
        )
    with stubbed():
        ok(await client.post(f"{BUDS}/{bud_of(made)}/restore", headers=d.pm.headers))

    async def stale(self: BoardHandoverRepository, card_id: uuid.UUID) -> Any:
        return await self._db.get(BoardCardHandover, row_id)

    count = await _buds(pg_session_factory, d.org)
    with stubbed(), patch.object(BoardHandoverRepository, "returned_discarded", stale):
        refused = await hand_over(client, d.pm, url)
    assert (refused.status_code, refused.json()["code"]) == (409, "BUD_NOT_RETURNED")
    assert await _buds(pg_session_factory, d.org) == count
