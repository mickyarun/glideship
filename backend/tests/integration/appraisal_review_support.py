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

"""Opening the Q4 2026 review in a test: October set up, two goals, review started."""

import uuid
from datetime import date

from httpx import AsyncClient
from sqlalchemy import update

from app.models.appraisal_cycle import AppraisalCycle
from tests.integration.appraisal_month import Month, october
from tests.integration.leave_support import Factory, as_user

BASE = "/api/v1/appraisals"


async def team_ids(client: AsyncClient, m: Month) -> dict[str, str]:
    """The manager's reports' appraisal ids, by name."""
    rows = (await client.get(f"{BASE}/team", headers=as_user(m.people["mgr"], m.org))).json()
    return {r["person_name"]: str(r["id"]) for r in rows}


async def cycle_id(client: AsyncClient, m: Month) -> str:
    """The org's one cycle."""
    (cycle,) = (await client.get(f"{BASE}/cycles", headers=as_user(m.people["hr"], m.org))).json()
    return str(cycle["id"])


async def end_period_early(factory: Factory, org: uuid.UUID) -> None:
    """Real time is inside Q4 2026; let the period end with October instead."""
    async with factory() as db:
        await db.execute(
            update(AppraisalCycle)
            .where(AppraisalCycle.org_id == org)
            .values(period_end=date(2026, 10, 31))
        )
        await db.commit()


async def started(
    client: AsyncClient, factory: Factory, *, ai: bool = False
) -> tuple[Month, dict[str, str], str]:
    """October with two goals for Priya, then the review opened."""
    m = await october(client, factory, ai=ai)
    ids, cycle = await team_ids(client, m), await cycle_id(client, m)
    mgr, hr = as_user(m.people["mgr"], m.org), as_user(m.people["hr"], m.org)
    goals_url = f"{BASE}/{ids['Priya']}/goals"
    for title in ("Ship refunds", "Automate UAT"):
        body = {"title": title, "reason": "Q4 focus"}
        added = await client.post(goals_url, json=body, headers=mgr)
        assert added.status_code == 201
    early = await client.post(f"{BASE}/cycles/{cycle}/start-review", headers=hr)
    assert early.status_code == 409
    await end_period_early(factory, m.org)
    opened = await client.post(f"{BASE}/cycles/{cycle}/start-review", headers=hr)
    assert opened.status_code == 202 and opened.json() == {"opened": 2}
    return m, ids, cycle
