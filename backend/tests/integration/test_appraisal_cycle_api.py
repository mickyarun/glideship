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

"""HR's appraisal setup over the API: settings, cycles, enrolment, templates."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.appraisal import Appraisal
from app.models.appraisal_enums import AppraisalStatus, DraftingMode
from app.repositories.employee_profile import EmployeeProfileRepository
from app.services.appraisals.enrolment import follow_primary_manager, withdraw_on_exit
from tests.integration.leave_support import (
    Factory,
    add_member_without_profile,
    as_user,
    give_role,
    report_to,
    setup_org,
)

pytestmark = pytest.mark.integration
BASE = "/api/v1/appraisals"


async def _org(factory: Factory) -> tuple[uuid.UUID, dict[str, uuid.UUID]]:
    org, ids, _ = await setup_org(factory, "Hr", "Ravi", "Priya", "Lone", "Meena")
    people = dict(zip(("hr", "mgr", "emp", "lone", "other"), ids, strict=True))
    await give_role(factory, org, people["hr"], "hr")
    await report_to(factory, org, people["emp"], people["mgr"])
    await report_to(factory, org, people["mgr"], people["hr"])
    await report_to(factory, org, people["other"], people["mgr"])
    return org, people


async def _cycle(client: AsyncClient, org: uuid.UUID, hr: uuid.UUID, **body: object) -> dict:
    created = await client.post(
        f"{BASE}/cycles", json={"period_start": "2026-10-01", **body}, headers=as_user(hr, org)
    )
    assert created.status_code == 201, created.text
    return created.json()


async def test_settings_default_and_reject_cadences_that_dont_fit(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, p = await _org(pg_session_factory)
    hr = as_user(p["hr"], org)
    got = await client.get(f"{BASE}/settings", headers=hr)
    assert got.json()["review_period"] == "quarterly"
    assert got.json()["feedback_cadence"] == "monthly"
    bad = {**got.json(), "feedback_cadence": "quarterly"}
    assert (await client.put(f"{BASE}/settings", json=bad, headers=hr)).status_code == 422
    good = {**got.json(), "feedback_cadence": "in_review", "ai_enabled": False}
    assert (await client.put(f"{BASE}/settings", json=good, headers=hr)).status_code == 200
    assert (await client.get(f"{BASE}/settings", headers=hr)).json()[
        "feedback_cadence"
    ] == "in_review"


async def test_only_hr_reaches_setup(client: AsyncClient, pg_session_factory: Factory) -> None:
    org, p = await _org(pg_session_factory)
    for who in ("mgr", "emp"):
        got = await client.get(f"{BASE}/settings", headers=as_user(p[who], org))
        assert got.status_code == 403


async def test_new_cycle_is_prefilled_from_settings(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, p = await _org(pg_session_factory)
    cycle = await _cycle(client, org, p["hr"])
    assert cycle["name"] == "Q4 2026"
    assert (cycle["period_end"], cycle["self_due"]) == ("2026-12-31", "2027-01-07")
    assert cycle["status"] == "draft" and cycle["enrolment_cutoff"] == "2026-10-31"
    assert cycle["reminder_offsets"] == [-3, 0, 2]


async def test_activation_enrols_people_with_a_primary_manager(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, p = await _org(pg_session_factory)
    stub = await add_member_without_profile(pg_session_factory, org, "Stub")
    cycle = await _cycle(client, org, p["hr"], ai_drafting=False)
    report = await client.post(
        f"{BASE}/cycles/{cycle['id']}/activate", headers=as_user(p["hr"], org)
    )
    assert report.status_code == 200, report.text
    body = report.json()
    # hr, mgr, emp and other have a primary manager or report to someone above;
    # lone has none and stub has no employee record at all.
    assert str(p["lone"]) in body["no_primary_manager"]
    assert str(stub) not in body["no_primary_manager"]
    async with pg_session_factory() as db:
        rows = list(
            await db.scalars(select(Appraisal).where(Appraisal.cycle_id == uuid.UUID(cycle["id"])))
        )
    assert len(rows) == body["enrolled"] == 3
    assert {r.drafting_mode for r in rows} == {DraftingMode.MANUAL}
    again = await client.post(
        f"{BASE}/cycles/{cycle['id']}/activate", headers=as_user(p["hr"], org)
    )
    assert again.status_code == 409


async def test_overlapping_cycles_cannot_both_run(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, p = await _org(pg_session_factory)
    first = await _cycle(client, org, p["hr"])
    second = await _cycle(client, org, p["hr"], name="Q4 again")
    hr = as_user(p["hr"], org)
    assert (
        await client.post(f"{BASE}/cycles/{first['id']}/activate", headers=hr)
    ).status_code == 200
    clash = await client.post(f"{BASE}/cycles/{second['id']}/activate", headers=hr)
    assert clash.status_code == 409 and "Q4 2026" in clash.json()["detail"]


async def test_running_cycle_cannot_be_edited_or_deleted(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, p = await _org(pg_session_factory)
    cycle = await _cycle(client, org, p["hr"])
    hr = as_user(p["hr"], org)
    await client.post(f"{BASE}/cycles/{cycle['id']}/activate", headers=hr)
    assert (
        await client.patch(f"{BASE}/cycles/{cycle['id']}", json={"name": "X"}, headers=hr)
    ).status_code == 409
    assert (await client.delete(f"{BASE}/cycles/{cycle['id']}", headers=hr)).status_code == 409


async def test_templates_are_seeded_and_the_fallback_stays(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, p = await _org(pg_session_factory)
    hr = as_user(p["hr"], org)
    templates = (await client.get(f"{BASE}/role-templates", headers=hr)).json()
    assert len(templates) == 11
    general = next(t for t in templates if t["is_default"])
    assert (
        await client.delete(f"{BASE}/role-templates/{general['id']}", headers=hr)
    ).status_code == 409
    support = next(t for t in templates if t["name"] == "Support")
    assert (
        await client.delete(f"{BASE}/role-templates/{support['id']}", headers=hr)
    ).status_code == 204
    # Deleting one never brings the seed back.
    assert len((await client.get(f"{BASE}/role-templates", headers=hr)).json()) == 10


async def test_exit_withdraws_and_a_new_manager_takes_over(
    client: AsyncClient, pg_session_factory: Factory
) -> None:
    org, p = await _org(pg_session_factory)
    cycle = await _cycle(client, org, p["hr"])
    await client.post(f"{BASE}/cycles/{cycle['id']}/activate", headers=as_user(p["hr"], org))
    await report_to(pg_session_factory, org, p["emp"], p["other"])
    async with pg_session_factory() as db:
        profile = await EmployeeProfileRepository(db, org_id=org).get_by_user(p["emp"])
        assert profile is not None
        assert await follow_primary_manager(db, org, profile, p["hr"]) == 1
        assert await withdraw_on_exit(db, org, profile.id) == 1
        await db.commit()
        row = await db.scalar(
            select(Appraisal).where(
                Appraisal.cycle_id == uuid.UUID(cycle["id"]), Appraisal.profile_id == profile.id
            )
        )
    assert row is not None
    assert row.manager_user_id == p["other"]
    assert row.status is AppraisalStatus.WITHDRAWN
