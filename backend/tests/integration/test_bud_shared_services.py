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

"""The BUD services shared by the API and board handover, on real Postgres.

``discard_bud`` must leave a BUD exactly as ``PATCH {status: discarded}``
does, and ``find_nearest_active`` ranks open BUDs only, nearest first.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.bud import BUDStatus, BUDTimelineEvent
from app.models.bud_version import BUDVersion
from app.models.feature import Feature
from app.repositories.bud import BUDRepository
from app.services.bud_discard import BUDNotDiscardableError, discard_bud
from app.services.jira_dedup import THRESHOLD_REVIEW
from tests.integration.bud_lifecycle_reads import load_bud, timeline
from tests.integration.bud_lifecycle_support import (
    Factory,
    add_bud,
    add_member,
    as_user,
    new_org,
    stub_externals,
)
from tests.integration.bud_lifecycle_support import (
    app_database_blocked as app_database_blocked,
)
from tests.integration.scan_features_bugs_support import new_bud, vec

pytestmark = pytest.mark.integration


async def _discard_outcome(factory: Factory, bud_id: uuid.UUID) -> dict[str, Any]:
    """Everything a discard writes, in a form two runs can be compared on."""
    bud = await load_bud(factory, bud_id)
    changes = await timeline(factory, bud_id, "status_change")
    async with factory() as db:
        versions = (await db.scalars(select(BUDVersion).where(BUDVersion.bud_id == bud_id))).all()
        active = await db.scalar(select(Feature.is_active).where(Feature.org_id == bud.org_id))
    return {
        "status": bud.status,
        "changes": [(c["from"], c["to"]) for c in changes],
        "versions": [(v.phase, v.source, v.version_no) for v in versions],
        "feature_active": active,
    }


async def _bud_with_feature(client: AsyncClient, factory: Factory) -> tuple[str, Any]:
    org = await new_org(factory)
    pm = await add_member(factory, org, "pm")
    with stub_externals():
        res = await client.post(
            "/api/v1/buds/", json={"title": "Checkout"}, headers=as_user(pm, org)
        )
    assert res.status_code == 201, res.text
    return res.json()["id"], (org, pm)


async def test_discard_bud_matches_the_status_patch(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    """Same status, timeline, version row and inactive feature as the PATCH."""
    patched, (org, pm) = await _bud_with_feature(client, pg_session_factory)
    with stub_externals():
        res = await client.patch(
            f"/api/v1/buds/{patched}", json={"status": "discarded"}, headers=as_user(pm, org)
        )
    assert res.status_code == 200, res.text

    served, (org2, pm2) = await _bud_with_feature(client, pg_session_factory)
    async with pg_session_factory() as db:
        bud = await BUDRepository(db, org_id=org2).get_by_id(uuid.UUID(served))
        assert bud is not None
        with stub_externals():
            await discard_bud(db, org2, bud, actor_id=pm2, actor_name="pm")
        await db.commit()

    want = await _discard_outcome(pg_session_factory, uuid.UUID(patched))
    assert want["status"] is BUDStatus.DISCARDED and want["feature_active"] is False
    assert await _discard_outcome(pg_session_factory, uuid.UUID(served)) == want
    async with pg_session_factory() as db:
        actors = await db.scalars(
            select(BUDTimelineEvent.actor_id).where(
                BUDTimelineEvent.bud_id == uuid.UUID(served),
                BUDTimelineEvent.event_type == "status_change",
            )
        )
        assert list(actors) == [pm2]


async def test_discard_bud_refuses_a_closed_bud(pg_session_factory: Factory) -> None:
    """A closed BUD can't be discarded from code either."""
    org = await new_org(pg_session_factory)
    bud_id = await add_bud(pg_session_factory, org, status=BUDStatus.CLOSED)
    async with pg_session_factory() as db:
        bud = await BUDRepository(db, org_id=org).get_by_id(bud_id)
        assert bud is not None
        with pytest.raises(BUDNotDiscardableError):
            await discard_bud(db, org, bud, actor_id=uuid.uuid4(), actor_name=None)


async def test_find_nearest_active_ranks_open_buds_under_the_threshold(
    pg_session_factory: Factory,
) -> None:
    """Nearest first, closed/discarded and too-far BUDs left out, scoped to the org."""
    org, other = await new_org(pg_session_factory), await new_org(pg_session_factory)
    near = await new_bud(
        pg_session_factory, org, 1, status=BUDStatus.DESIGN, embedding=vec(1, 0.1)
    )
    nearer = await new_bud(pg_session_factory, org, 2, status=BUDStatus.BUD, embedding=vec(1))
    await new_bud(pg_session_factory, org, 3, status=BUDStatus.CLOSED, embedding=vec(1))
    await new_bud(pg_session_factory, org, 4, status=BUDStatus.DISCARDED, embedding=vec(1))
    await new_bud(pg_session_factory, org, 5, status=BUDStatus.BUD, embedding=vec(0, 1))
    await new_bud(pg_session_factory, other, 1, status=BUDStatus.BUD, embedding=vec(1))

    async with pg_session_factory() as db:
        repo = BUDRepository(db, org_id=org)
        ranked = await repo.find_nearest_active(vec(1), 10, max_distance=THRESHOLD_REVIEW)
        capped = await repo.find_nearest_active(vec(1), 1)
        everything = await repo.find_nearest_active(vec(1), 10)

    assert [bud.id for bud, _ in ranked] == [nearer, near]
    assert ranked[0][1] == pytest.approx(0.0, abs=1e-6)
    assert [bud.id for bud, _ in capped] == [nearer]
    assert len(everything) == 3
