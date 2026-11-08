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

"""The end-of-period review: start, self-score, manager review, calibration, result."""

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.appraisal import Appraisal
from app.models.employee_audit_event import EmployeeAuditAction, EmployeeAuditEvent
from app.services.file_storage import FileStorage
from tests.integration.appraisal_month import run_tick
from tests.integration.appraisal_review_support import started
from tests.integration.hr_support import configure_hr_storage
from tests.integration.leave_support import Factory, as_user

pytestmark = pytest.mark.integration
BASE = "/api/v1/appraisals"


@pytest.fixture
def hr_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FileStorage:
    """The shared test HR key (see ``hr_support``)."""
    return configure_hr_storage(monkeypatch, tmp_path)


async def _actions(factory: Factory, org: uuid.UUID, action: EmployeeAuditAction) -> int:
    async with factory() as db:
        rows = await db.scalars(
            select(EmployeeAuditEvent).where(
                EmployeeAuditEvent.org_id == org, EmployeeAuditEvent.action == action
            )
        )
        return len(rows.all())


async def test_a_review_from_self_score_to_acknowledgement(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m, ids, cycle = await started(client, pg_session_factory)
    emp, mgr = as_user(m.people["emp"], m.org), as_user(m.people["mgr"], m.org)
    hr = as_user(m.people["hr"], m.org)
    url = f"{BASE}/{ids['Priya']}"
    review = (await client.get(url, headers=emp)).json()
    assert review["status"] == "self_review" and review["can"]["edit_self"]
    assert review["manager_score"] is None and review["manager_only"] is None
    goals = {g["title"]: g["id"] for g in review["goals"]}
    fact = review["timeline"][0]["facts"][0]["id"]
    locked = await client.post(f"{url}/goals", json={"title": "Late"}, headers=emp)
    assert locked.status_code == 409
    unknown = {"band": 3, "evidence": ["not-a-fact"]}
    assert (await client.put(f"{url}/self", json=unknown, headers=emp)).status_code == 422
    self_body = {
        "band": 2,
        "reason": "Shipped refunds",
        "evidence": [fact],
        "goals": [
            {"goal_id": goals["Ship refunds"], "result": "achieved", "reason": "Live in Oct"},
            {"goal_id": goals["Automate UAT"], "result": "partly", "evidence": [fact]},
        ],
    }
    assert (await client.put(f"{url}/self", json=self_body, headers=emp)).status_code == 200
    two_needed = await client.post(f"{url}/self/submit", headers=emp)
    assert two_needed.status_code == 422 and "two pieces" in two_needed.json()["detail"]
    await client.put(f"{url}/self", json={**self_body, "band": 3}, headers=emp)
    submitted = await client.post(f"{url}/self/submit", headers=emp)
    assert submitted.json()["status"] == "manager_review"

    seen = (await client.get(url, headers=mgr)).json()
    assert seen["self_score"]["band"] == 3 and seen["can"]["edit_manager"]
    no_reason = {
        "agree": False,
        "band": 4,
        "reason": "Refunds slipped a sprint",
        "goals": [
            {"goal_id": goals["Ship refunds"], "agree": True},
            {"goal_id": goals["Automate UAT"], "agree": False, "result": "not_yet"},
        ],
        "ready_next_level": False,
        "performance_concern": True,
        "concern_note": "Watch delivery",
    }
    refused = await client.post(f"{url}/manager/submit", json=no_reason, headers=mgr)
    assert refused.status_code == 422
    body = {
        **no_reason,
        "goals": [no_reason["goals"][0], {**no_reason["goals"][1], "reason": "Suite not running"}],
    }
    sent = await client.post(f"{url}/manager/submit", json=body, headers=mgr)
    assert sent.status_code == 200 and sent.json()["status"] == "calibration"
    assert sent.json()["manager_score"]["final_band"] == 4

    hidden = (await client.get(url, headers=emp)).json()
    assert hidden["manager_score"] is None and hidden["manager_only"] is None
    assert all(g["result"] is None for g in hidden["goals"])
    calibration = (await client.get(f"{BASE}/cycles/{cycle}/calibration", headers=hr)).json()
    (team,) = calibration["teams"]
    assert team["manager_name"] == "Ravi" and team["agreement"] == 0 and team["bands"]["4"] == 1
    hr_view = (await client.get(url, headers=hr)).json()
    assert hr_view["manager_only"]["concern_note"] == "Watch delivery"

    back = await client.post(f"{url}/send-back", json={"note": "Explain the UAT call"}, headers=hr)
    assert back.json()["status"] == "manager_review"
    assert (await client.get(url, headers=mgr)).json()["send_back_note"] == "Explain the UAT call"
    assert (await client.get(url, headers=emp)).json()["send_back_note"] is None
    await client.post(f"{url}/manager/submit", json=body, headers=mgr)
    shared = await client.post(f"{url}/share", headers=hr)
    assert shared.json()["status"] == "shared"

    result = (await client.get(url, headers=emp)).json()
    assert result["manager_score"]["final_band"] == 4 and result["manager_only"] is None
    uat = next(g for g in result["goals"] if g["title"] == "Automate UAT")
    assert (uat["self_result"], uat["result"], uat["manager_reason"]) == (
        "partly",
        "not_yet",
        "Suite not running",
    )
    assert result["can"]["acknowledge"]
    done = await client.post(f"{url}/acknowledge", json={"reply": "Fair, thanks"}, headers=emp)
    assert done.json()["status"] == "acknowledged"
    assert (await client.get(url, headers=hr)).json()["reply"] == "Fair, thanks"
    for action, count in (
        (EmployeeAuditAction.APPRAISAL_SCORED, 2),
        (EmployeeAuditAction.APPRAISAL_SENT_BACK, 1),
        (EmployeeAuditAction.APPRAISAL_SHARED, 1),
    ):
        assert await _actions(pg_session_factory, m.org, action) == count


async def test_no_self_score_by_the_due_date_goes_to_the_manager_who_scores_from_scratch(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m, ids, cycle = await started(client, pg_session_factory)
    await run_tick(pg_session_factory, m.org, datetime(2027, 1, 8, 6, tzinfo=UTC))
    async with pg_session_factory() as db:
        status = await db.scalar(
            select(Appraisal.status).where(Appraisal.id == uuid.UUID(ids["Meena"]))
        )
    assert status is not None and status.value == "manager_review"
    mgr = as_user(m.people["mgr"], m.org)
    url = f"{BASE}/{ids['Meena']}/manager/submit"
    assert (await client.post(url, json={"agree": True}, headers=mgr)).status_code == 422
    scored = await client.post(url, json={"band": 3, "reason": "Steady month"}, headers=mgr)
    assert scored.status_code == 200 and scored.json()["manager_score"]["final_band"] == 3
    shared = await client.post(
        f"{BASE}/cycles/{cycle}/share", headers=as_user(m.people["hr"], m.org)
    )
    assert shared.json() == {"shared": 1}


async def test_only_the_right_people_act(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m, ids, _ = await started(client, pg_session_factory)
    url = f"{BASE}/{ids['Priya']}"
    stranger = as_user(m.people["stranger"], m.org)
    assert (await client.get(url, headers=stranger)).status_code == 404
    mgr = as_user(m.people["mgr"], m.org)
    assert (await client.put(f"{url}/self", json={"band": 1}, headers=mgr)).status_code == 409
    emp = as_user(m.people["emp"], m.org)
    assert (
        await client.post(f"{url}/manager/submit", json={"band": 1}, headers=emp)
    ).status_code == 409
    assert (await client.post(f"{url}/share", headers=emp)).status_code == 409
