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

"""The October 2026 scenario most check-in tests start from."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime

from httpx import AsyncClient

from app.models.board import BoardVisibility
from app.repositories.appraisal_cycle import orgs_with_running_cycles
from app.services.appraisals.check_in_scheduler import org_pass
from tests.integration.appraisal_support import done_card
from tests.integration.board_support import new_board
from tests.integration.leave_support import (
    Factory,
    add_request,
    as_user,
    give_role,
    report_to,
    setup_org,
)

NOV_2 = datetime(2026, 11, 2, 6, tzinfo=UTC)  # the first working day after October


@dataclass(frozen=True)
class Month:
    """The October set-up: the org, its people by role and the card that counts."""

    org: uuid.UUID
    people: dict[str, uuid.UUID]
    counted: uuid.UUID


async def run_tick(factory: Factory, org: uuid.UUID, now: datetime) -> None:
    """One check-in tick for one org at ``now``."""
    async with factory() as db:
        mine = [o for o in await orgs_with_running_cycles(db) if o.org_id == org]
        assert mine
        await org_pass(db, mine[0], now)
        await db.commit()


async def october(client: AsyncClient, factory: Factory, *, ai: bool = False) -> Month:
    """An org with HR, a manager and two reports, one with October work and leave.

    Opens a Q4 2026 cycle and runs the tick on the first working day after October.
    """
    org, ids, _ = await setup_org(factory, "Hr", "Ravi", "Priya", "Meena", "Sam")
    p = dict(zip(("hr", "mgr", "emp", "quiet", "stranger"), ids, strict=True))
    await give_role(factory, org, p["hr"], "hr")
    for person in ("emp", "quiet"):
        await report_to(factory, org, p[person], p["mgr"])
    board = await new_board(factory, org, visibility=BoardVisibility.MEMBERS)
    counted = await done_card(factory, board, p["emp"], datetime(2026, 10, 15, 9, tzinfo=UTC))
    await done_card(
        factory, board, p["emp"], datetime(2026, 10, 16, 9, tzinfo=UTC), still_done=False
    )
    await done_card(factory, board, p["emp"], datetime(2026, 11, 1, 12, tzinfo=UTC))
    await add_request(factory, org, p["emp"], date(2026, 10, 20), date(2026, 10, 21), "2")
    hr = as_user(p["hr"], org)
    cycle = await client.post(
        "/api/v1/appraisals/cycles",
        json={"period_start": "2026-10-01", "ai_drafting": ai},
        headers=hr,
    )
    activated = await client.post(
        f"/api/v1/appraisals/cycles/{cycle.json()['id']}/activate", headers=hr
    )
    assert activated.status_code == 200, activated.text
    await run_tick(factory, org, NOV_2)
    return Month(org, p, counted)
