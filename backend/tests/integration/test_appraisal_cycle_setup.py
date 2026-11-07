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

"""Cycle setup for HR: editing a draft, readiness, progress, closing, and the guide."""

import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.services.file_storage import FileStorage
from tests.integration.appraisal_month import october
from tests.integration.hr_support import configure_hr_storage
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


@pytest.fixture
def hr_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FileStorage:
    """The shared test HR key (see ``hr_support``)."""
    return configure_hr_storage(monkeypatch, tmp_path)


async def _org(factory: Factory) -> tuple[uuid.UUID, dict[str, uuid.UUID]]:
    org, ids, _ = await setup_org(factory, "Hr", "Ravi", "Priya", "Lone")
    people = dict(zip(("hr", "mgr", "emp", "lone"), ids, strict=True))
    await give_role(factory, org, people["hr"], "hr")
    await report_to(factory, org, people["emp"], people["mgr"])
    await report_to(factory, org, people["mgr"], people["hr"])
    return org, people


async def _draft(client: AsyncClient, org: uuid.UUID, hr: uuid.UUID, **body: object) -> str:
    created = await client.post(
        f"{BASE}/cycles", json={"period_start": "2026-10-01", **body}, headers=as_user(hr, org)
    )
    assert created.status_code == 201, created.text
    return str(created.json()["id"])


async def test_readiness_lists_what_hr_should_fix(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    org, p = await _org(pg_session_factory)
    await add_member_without_profile(pg_session_factory, org, "Priya")
    hr = as_user(p["hr"], org)
    cycle = await _draft(client, org, p["hr"], ai_drafting=False)
    ready = (await client.get(f"{BASE}/cycles/{cycle}/readiness", headers=hr)).json()
    assert ready["in_scope"] == 4
    assert [r["name"] for r in ready["no_primary_manager"]] == ["Hr", "Lone"]
    assert [(f["name"], [x["name"] for x in f["maybe"]]) for f in ready["identity"]] == [
        ("Priya", ["Priya"])
    ]
    assert ready["drafting"] == "manual"
    assert ready["ai_note"] == "AI drafting is off for this cycle."
    await client.patch(f"{BASE}/cycles/{cycle}", json={"ai_drafting": True}, headers=hr)
    ready = (await client.get(f"{BASE}/cycles/{cycle}/readiness", headers=hr)).json()
    assert ready["drafting"] == "ai" and ready["ai_note"] is None
    emp = as_user(p["emp"], org)
    assert (await client.get(f"{BASE}/cycles/{cycle}/readiness", headers=emp)).status_code == 403


async def test_a_draft_takes_cadence_reminder_and_note_changes(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    org, p = await _org(pg_session_factory)
    hr = as_user(p["hr"], org)
    cycle = await _draft(client, org, p["hr"])
    url = f"{BASE}/cycles/{cycle}"
    bad = await client.patch(url, json={"feedback_cadence": "quarterly"}, headers=hr)
    assert bad.status_code == 422
    far = await client.patch(url, json={"reminder_offsets": [-11]}, headers=hr)
    assert far.status_code == 422
    changes = {
        "feedback_cadence": "in_review",
        "overdue_nudge": False,
        "hr_overdue_offset": 5,
        "intro_note": "Reviews close before the offsite.",
    }
    saved = await client.patch(url, json=changes, headers=hr)
    assert saved.status_code == 200, saved.text
    got = (await client.get(url, headers=hr)).json()
    assert got["feedback_cadence"] == "in_review"
    assert got["overdue_nudge"] is False and got["hr_overdue_offset"] == 5
    assert got["intro_note"] == "Reviews close before the offsite."


async def test_progress_counts_and_closing_locks_everything(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    hr = as_user(m.people["hr"], m.org)
    (cycle,) = (await client.get(f"{BASE}/cycles", headers=hr)).json()
    progress = (await client.get(f"{BASE}/cycles/{cycle['id']}/progress", headers=hr)).json()
    rows = {r["name"]: r for r in progress["people"]}
    assert rows["Priya"]["manager_name"] == "Ravi"
    assert (rows["Priya"]["check_ins"], rows["Priya"]["feedback"]) == (1, 1)
    assert progress["feedback"] == 2 and progress["feedback_done"] == 0
    closed = await client.post(f"{BASE}/cycles/{cycle['id']}/close", headers=hr)
    assert closed.status_code == 200 and closed.json()["status"] == "closed"
    mgr = as_user(m.people["mgr"], m.org)
    item = (await client.get("/api/v1/manager-feedback/team", headers=mgr)).json()[0]
    refused = await client.put(
        f"/api/v1/manager-feedback/{item['id']}",
        json={"keep": "a", "try_next": "b"},
        headers=mgr,
    )
    assert refused.status_code == 409
    draft = await _draft(client, m.org, m.people["hr"], period_start="2027-01-01")
    assert (await client.post(f"{BASE}/cycles/{draft}/close", headers=hr)).status_code == 409


async def test_the_guide_uses_the_running_cycle_and_knows_the_audience(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    org, p = await _org(pg_session_factory)
    emp, mgr = as_user(p["emp"], org), as_user(p["mgr"], org)
    before = (await client.get("/api/v1/check-ins/guide", headers=emp)).json()
    assert before["cycle_name"] is None and before["review_period"] == "quarterly"
    hr = as_user(p["hr"], org)
    cycle = await _draft(client, org, p["hr"], intro_note="Ask HR anything.")
    await client.post(f"{BASE}/cycles/{cycle}/activate", headers=hr)
    guide = (await client.get("/api/v1/check-ins/guide", headers=emp)).json()
    assert guide["cycle_name"] == "Q4 2026" and guide["intro_note"] == "Ask HR anything."
    assert guide["self_due"] == "2027-01-07"
    assert (guide["is_manager"], guide["is_hr"]) == (False, False)
    assert (await client.get("/api/v1/check-ins/guide", headers=mgr)).json()["is_manager"]
    assert (await client.get("/api/v1/check-ins/guide", headers=hr)).json()["is_hr"]
