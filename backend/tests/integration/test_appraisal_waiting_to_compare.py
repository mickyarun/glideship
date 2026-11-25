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

"""A high-rating team waits for another team's reviews before its results can go out."""

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.models.appraisal import Appraisal
from app.models.appraisal_enums import AppraisalStatus, CycleStatus, DraftingMode
from app.repositories.employee_profile import EmployeeProfileRepository
from app.services.file_storage import FileStorage
from tests.integration.appraisal_support import cycle_row
from tests.integration.hr_support import configure_hr_storage
from tests.integration.leave_support import Factory, as_user, give_role, report_to, setup_org

pytestmark = pytest.mark.integration
BASE = "/api/v1/appraisals"


@pytest.fixture
def hr_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FileStorage:
    """The shared test HR key (see ``hr_support``)."""
    return configure_hr_storage(monkeypatch, tmp_path)


async def _two_teams(factory: Factory) -> tuple[uuid.UUID, dict[str, uuid.UUID], str]:
    """Ana's three reviews in HR's hands, all Exceeded; Bo's one still being written."""
    org, ids, _ = await setup_org(factory, "Hr", "Ana", "Bo", "Pia", "Paz", "Pet", "Quin")
    p = dict(zip(("hr", "ana", "bo", "pia", "paz", "pet", "quin"), ids, strict=True))
    await give_role(factory, org, p["hr"], "hr")
    for person in ("pia", "paz", "pet"):
        await report_to(factory, org, p[person], p["ana"])
    await report_to(factory, org, p["quin"], p["bo"])
    async with factory() as db:
        cycle = cycle_row(org, status=CycleStatus.REVIEWING)
        db.add(cycle)
        await db.flush()
        profiles = EmployeeProfileRepository(db, org_id=org)
        for person, manager in (("pia", "ana"), ("paz", "ana"), ("pet", "ana"), ("quin", "bo")):
            profile = await profiles.get_by_user(p[person])
            assert profile is not None
            in_hand = manager == "ana"
            appraisal = Appraisal(
                org_id=org,
                cycle_id=cycle.id,
                profile_id=profile.id,
                manager_user_id=p[manager],
                drafting_mode=DraftingMode.MANUAL,
                status=AppraisalStatus.CALIBRATION if in_hand else AppraisalStatus.MANAGER_REVIEW,
                manager_submitted_at=datetime.now(UTC) if in_hand else None,
                manager_band=1 if in_hand else None,
                final_band=1 if in_hand else None,
            )
            db.add(appraisal)
            await db.flush()
            p[f"{person}_review"] = appraisal.id
        await db.commit()
        return org, p, str(cycle.id)


async def _calibration(client: AsyncClient, cycle: str, hr: dict[str, str]) -> dict[str, Any]:
    got = await client.get(f"{BASE}/cycles/{cycle}/calibration", headers=hr)
    assert got.status_code == 200, got.text
    return dict(got.json())


async def test_a_team_alone_waits_until_another_team_is_in(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    org, p, cycle = await _two_teams(pg_session_factory)
    hr = as_user(p["hr"], org)
    cal = await _calibration(client, cycle, hr)
    ana = next(t for t in cal["teams"] if t["manager_name"] == "Ana")
    assert ana["waiting"] and not ana["rates_high"]
    assert all(person["held"] for person in cal["people"] if person["manager_name"] == "Ana")
    # Nothing goes out while Ana's team can't be compared.
    assert (await client.post(f"{BASE}/cycles/{cycle}/share", headers=hr)).json() == {"shared": 0}

    # HR can release one early with "Looks fair", while Bo's team is still absent.
    fair = {"appraisal_ids": [str(p["pia_review"])]}
    marked = await client.post(f"{BASE}/cycles/{cycle}/looks-fair", json=fair, headers=hr)
    assert marked.json() == {"marked": 1}
    assert (await client.post(f"{BASE}/cycles/{cycle}/share", headers=hr)).json() == {"shared": 1}

    # Bo's review arrives, also Exceeded: Ana no longer stands out, so nothing is held.
    async with pg_session_factory() as db:
        await db.execute(
            update(Appraisal)
            .where(Appraisal.id == p["quin_review"])
            .values(
                status=AppraisalStatus.CALIBRATION,
                manager_submitted_at=datetime.now(UTC),
                manager_band=2,
                final_band=2,
            )
        )
        await db.commit()
    cal = await _calibration(client, cycle, hr)
    ana = next(t for t in cal["teams"] if t["manager_name"] == "Ana")
    assert not ana["waiting"] and not ana["rates_high"]
    assert not any(person["held"] for person in cal["people"])
    assert (await client.post(f"{BASE}/cycles/{cycle}/share", headers=hr)).json() == {"shared": 3}


async def test_once_compared_the_usual_rule_holds_a_team_that_stands_out(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    org, p, cycle = await _two_teams(pg_session_factory)
    hr = as_user(p["hr"], org)
    async with pg_session_factory() as db:
        await db.execute(
            update(Appraisal)
            .where(Appraisal.id == p["quin_review"])
            .values(
                status=AppraisalStatus.CALIBRATION,
                manager_submitted_at=datetime.now(UTC),
                manager_band=3,
                final_band=3,
            )
        )
        await db.commit()
    cal = await _calibration(client, cycle, hr)
    ana = next(t for t in cal["teams"] if t["manager_name"] == "Ana")
    assert ana["rates_high"] and not ana["waiting"]
    # Only Bo's review can go; Ana's three wait for "Looks fair".
    assert (await client.post(f"{BASE}/cycles/{cycle}/share", headers=hr)).json() == {"shared": 1}
