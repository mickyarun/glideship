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

"""Growth conversation rules: who writes, the goal limits, and when next goals lock."""

import uuid
from datetime import date
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.models.appraisal_cycle import AppraisalCycle
from app.services.file_storage import FileStorage
from tests.integration.appraisal_month import Month
from tests.integration.appraisal_review_support import BASE, started
from tests.integration.hr_support import configure_hr_storage
from tests.integration.leave_support import Factory, as_user

pytestmark = pytest.mark.integration


@pytest.fixture
def hr_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FileStorage:
    """The shared test HR key (see ``hr_support``)."""
    return configure_hr_storage(monkeypatch, tmp_path)


async def shared(client: AsyncClient, factory: Factory) -> tuple[Month, str]:
    """Priya's Q4 review scored and shared; her appraisal's URL."""
    m, ids, _ = await started(client, factory)
    emp, mgr = as_user(m.people["emp"], m.org), as_user(m.people["mgr"], m.org)
    url = f"{BASE}/{ids['Priya']}"
    review = (await client.get(url, headers=emp)).json()
    goals = [{"goal_id": g["id"], "result": "achieved"} for g in review["goals"]]
    await client.put(f"{url}/self", json={"band": 3, "goals": goals}, headers=emp)
    await client.post(f"{url}/self/submit", headers=emp)
    agree = {"agree": True, "goals": [{"goal_id": g["goal_id"], "agree": True} for g in goals]}
    await client.post(f"{url}/manager/submit", json=agree, headers=mgr)
    done = await client.post(f"{url}/share", headers=as_user(m.people["hr"], m.org))
    assert done.status_code == 200, done.text
    return m, url


async def next_cycle(client: AsyncClient, m: Month, scope: dict[str, list[str]]) -> str:
    """Open the cycle after Q4; its id."""
    hr = as_user(m.people["hr"], m.org)
    body = {"period_start": "2026-11-01", "scope": scope}
    made = await client.post(f"{BASE}/cycles", json=body, headers=hr)
    assert made.status_code == 201, made.text
    opened = await client.post(f"{BASE}/cycles/{made.json()['id']}/activate", headers=hr)
    assert opened.status_code == 200, opened.text
    return str(made.json()["id"])


async def test_who_writes_and_the_goal_limits(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m, url = await shared(client, pg_session_factory)
    emp, mgr = as_user(m.people["emp"], m.org), as_user(m.people["mgr"], m.org)
    hr = as_user(m.people["hr"], m.org)
    talk = {"strength": "Clear writing", "focus": "Estimate smaller"}
    assert (await client.put(f"{url}/growth", json=talk, headers=hr)).status_code == 409

    proposal = (
        await client.post(f"{url}/next-goals", json={"title": "Own a release"}, headers=emp)
    ).json()["growth"]["goals"][0]
    for title in ("One", "Two", "Three"):
        body = {"title": title}
        assert (await client.post(f"{url}/next-goals", json=body, headers=mgr)).status_code == 201
    full = await client.post(f"{url}/next-goals", json={"title": "Four"}, headers=mgr)
    assert full.status_code == 409
    accept = await client.post(f"{url}/next-goals/{proposal['id']}/accept", headers=mgr)
    assert accept.status_code == 409
    for title in ("P2", "P3"):
        body = {"title": title}
        assert (await client.post(f"{url}/next-goals", json=body, headers=emp)).status_code == 201
    capped = await client.post(f"{url}/next-goals", json={"title": "P4"}, headers=emp)
    assert capped.status_code == 409

    # Once the manager confirms a proposal, it's no longer the employee's to take back.
    growth = (await client.get(url, headers=emp)).json()["growth"]
    p2 = next(g for g in growth["goals"] if g["title"] == "P2")
    one = next(g for g in growth["goals"] if g["title"] == "One")
    two = next(g for g in growth["goals"] if g["title"] == "Two")
    gone = await client.delete(f"{url}/next-goals/{one['id']}", headers=mgr)
    assert gone.status_code == 200
    confirm = await client.post(f"{url}/next-goals/{p2['id']}/accept", headers=mgr)
    assert confirm.status_code == 200
    assert (await client.delete(f"{url}/next-goals/{p2['id']}", headers=emp)).status_code == 409
    assert (await client.delete(f"{url}/next-goals/{two['id']}", headers=emp)).status_code == 409
    mine = await client.delete(f"{url}/next-goals/{proposal['id']}", headers=emp)
    assert mine.status_code == 200


async def test_growth_outlives_the_cycle_and_locks_with_the_next_review(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m, url = await shared(client, pg_session_factory)
    emp, mgr = as_user(m.people["emp"], m.org), as_user(m.people["mgr"], m.org)
    hr = as_user(m.people["hr"], m.org)
    (q4,) = (await client.get(f"{BASE}/cycles", headers=hr)).json()
    old = str(q4["id"])
    assert (await client.post(f"{BASE}/cycles/{old}/close", headers=hr)).status_code == 200
    talk = {"strength": "Calm in incidents", "focus": "Delegate more"}
    assert (await client.put(f"{url}/growth", json=talk, headers=mgr)).status_code == 200

    # A cycle that doesn't cover Priya leaves her goals waiting.
    await next_cycle(client, m, {"departments": ["Nobody here"]})
    body = {"title": "Mentor a new joiner"}
    assert (await client.post(f"{url}/next-goals", json=body, headers=mgr)).status_code == 201
    async with pg_session_factory() as db:
        await db.execute(
            update(AppraisalCycle)
            .where(AppraisalCycle.org_id == m.org, AppraisalCycle.id != uuid.UUID(old))
            .values(status="closed")
        )
        await db.commit()

    # Her own next cycle picks them up, and later goals join it at once.
    new_cycle = await next_cycle(client, m, {})
    later = {"title": "Run a retro"}
    assert (await client.post(f"{url}/next-goals", json=later, headers=mgr)).status_code == 201
    rows = (await client.get(f"{BASE}/mine", headers=emp)).json()
    new = next(r for r in rows if r["period_start"] == "2026-11-01")
    page = (await client.get(f"{BASE}/{new['id']}/goals", headers=emp)).json()
    assert {g["title"] for g in page["goals"] if g["status"] == "accepted"} == {
        "Mentor a new joiner",
        "Run a retro",
    }

    async with pg_session_factory() as db:
        await db.execute(
            update(AppraisalCycle)
            .where(AppraisalCycle.id == uuid.UUID(new_cycle))
            .values(period_end=date(2026, 11, 5), enrolment_cutoff=date(2026, 11, 1))
        )
        await db.commit()
    review = await client.post(f"{BASE}/cycles/{new_cycle}/start-review", headers=hr)
    assert review.status_code == 202, review.text
    locked = await client.post(f"{url}/next-goals", json={"title": "Too late"}, headers=mgr)
    assert locked.status_code == 409
    # The strength and focus stay open; only next period's goals lock.
    assert (await client.put(f"{url}/growth", json=talk, headers=emp)).status_code == 200
