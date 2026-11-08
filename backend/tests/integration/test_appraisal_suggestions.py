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

"""Suggested goals through the sweeper, and a role's trends from draft to approval."""

import json
import uuid
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.appraisal import Appraisal
from app.models.appraisal_ai_run import AppraisalAiRun
from app.models.appraisal_enums import DraftKind
from app.models.appraisal_goal import AppraisalGoal
from app.models.appraisal_role_template import AppraisalRoleTemplate
from app.services.appraisals import draft_sweeper, trend_draft_job
from app.services.claude_runner import ClaudeRunResult
from app.services.file_storage import FileStorage
from tests.integration.appraisal_model import Model, model
from tests.integration.appraisal_month import Month, october
from tests.integration.hr_support import configure_hr_storage
from tests.integration.leave_support import Factory, as_user

pytestmark = pytest.mark.integration
__all__ = ["model"]  # the fixture, imported for pytest to find
BASE = "/api/v1/appraisals"


@pytest.fixture
def hr_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FileStorage:
    """The shared test HR key (see ``hr_support``)."""
    return configure_hr_storage(monkeypatch, tmp_path)


def _reply(*goals: dict[str, Any]) -> ClaudeRunResult:
    return ClaudeRunResult(success=True, output=json.dumps({"goals": list(goals)}))


def _goal(basis: str, cites: list[str], title: str = "Close tickets in 4 hours") -> dict[str, Any]:
    return {
        "title": title,
        "measure": "90% of tickets",
        "measure_source": "helpdesk report",
        "basis": basis,
        "why": "Builds on what came before",
        "cites": cites,
    }


async def _appraisal(client: AsyncClient, m: Month) -> str:
    mine = (await client.get(f"{BASE}/mine", headers=as_user(m.people["emp"], m.org))).json()
    return str(mine[0]["id"])


async def test_manual_mode_has_no_suggestions(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage, model: Model
) -> None:
    m = await october(client, pg_session_factory)
    url = f"{BASE}/{await _appraisal(client, m)}/suggest-goals"
    refused = await client.post(url, headers=as_user(m.people["emp"], m.org))
    assert refused.status_code == 409
    assert model.calls == []


async def test_a_new_joiner_gets_library_suggestions_that_wait_for_a_person(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage, model: Model
) -> None:
    m = await october(client, pg_session_factory, ai=True)
    emp = as_user(m.people["emp"], m.org)
    appraisal = await _appraisal(client, m)
    asked = await client.post(f"{BASE}/{appraisal}/suggest-goals", headers=emp)
    assert asked.status_code == 202 and asked.json()["suggest_status"] == "pending"
    model.reply = lambda _p: _reply(
        _goal("role_library", ["lib:0"]), _goal("feedback", ["feedback:x"], "Uncited")
    )
    await draft_sweeper.tick_once()
    assert "role library only" in model.calls[-1]
    goals = (await client.get(f"{BASE}/{appraisal}/goals", headers=emp)).json()
    (suggested,) = [g for g in goals["goals"] if g["status"] == "suggested"]
    assert (
        suggested["origin"] == "ai_suggested" and suggested["suggestion_basis"] == "role_library"
    )
    assert suggested["why"] == "Builds on what came before"
    assert suggested["measure"] == "90% of tickets · helpdesk report"
    assert goals["accepted"] == 0 and goals["suggest_status"] == "ready"
    taken = await client.post(f"{BASE}/goals/{suggested['id']}/accept", headers=emp)
    assert taken.json()["accepted"] == 1
    async with pg_session_factory() as db:
        kinds = (
            await db.scalars(select(AppraisalAiRun.kind).where(AppraisalAiRun.org_id == m.org))
        ).all()
    assert DraftKind.GOAL_SUGGESTIONS in kinds


async def test_feedback_and_approved_trends_reach_the_suggestions(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage, model: Model
) -> None:
    m = await october(client, pg_session_factory, ai=True)
    emp, mgr = as_user(m.people["emp"], m.org), as_user(m.people["mgr"], m.org)
    hr = as_user(m.people["hr"], m.org)
    appraisal = await _appraisal(client, m)
    item = next(
        r
        for r in (await client.get("/api/v1/manager-feedback/team", headers=mgr)).json()
        if r["person_name"] == "Priya"
    )
    await client.put(
        f"/api/v1/manager-feedback/{item['id']}",
        json={"keep": "Clear PRs", "try_next": "Answer support tickets faster"},
        headers=mgr,
    )
    async with pg_session_factory() as db:
        row = await db.get(Appraisal, uuid.UUID(appraisal))
        assert row is not None and row.role_template_id is not None
        template_id = row.role_template_id
    trend = {
        "id": "t1",
        "text": "Support moves to chat",
        "source_url": "https://a.test/s",
        "as_of": "2026-10",
    }
    put = await client.put(f"{BASE}/role-templates/{template_id}/trends", json=[trend], headers=hr)
    assert put.json()["trends_status"] == "draft"
    await client.post(f"{BASE}/{appraisal}/suggest-goals", headers=emp)
    model.reply = lambda _p: _reply(_goal("feedback", [f"feedback:{item['id']}"]))
    await draft_sweeper.tick_once()
    assert "Answer support tickets faster" in model.calls[-1]
    assert "Support moves to chat" not in model.calls[-1]  # not approved yet
    approved = await client.post(f"{BASE}/role-templates/{template_id}/trends/approve", headers=hr)
    assert approved.json()["trends_version"] == 1
    await client.post(f"{BASE}/{appraisal}/suggest-goals", headers=mgr)
    model.reply = lambda _p: _reply(_goal("trend", ["trend:t1"], "Run support chat"))
    await draft_sweeper.tick_once()
    assert "Support moves to chat" in model.calls[-1]
    async with pg_session_factory() as db:
        goals = (
            await db.scalars(select(AppraisalGoal).where(AppraisalGoal.org_id == m.org))
        ).all()
    live = [g for g in goals if g.status.value == "suggested"]
    assert len(live) == 1 and live[0].suggestion_refs["trends_version"] == 1
    assert sum(g.status.value == "dismissed" for g in goals) == 1
    cycle_url = f"{BASE}/cycles/{row.cycle_id}/suggest-goals"
    queued = await client.post(cycle_url, headers=hr)
    assert queued.status_code == 202 and queued.json() == {"queued": 2}


async def test_a_trend_draft_keeps_only_sourced_items(
    client: AsyncClient,
    pg_session_factory: Factory,
    hr_key: FileStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    m = await october(client, pg_session_factory)
    hr = as_user(m.people["hr"], m.org)
    templates = (await client.get(f"{BASE}/role-templates", headers=hr)).json()
    template_id = templates[0]["id"]
    seen: list[str] = []

    async def research(_org: uuid.UUID, prompt: str) -> ClaudeRunResult:
        seen.append(prompt)
        items = [
            {"text": "Tests are generated", "source_url": "https://a.test/t", "as_of": "2026-09"},
            {"text": "No source", "source_url": ""},
        ]
        return ClaudeRunResult(success=True, output=json.dumps({"trends": items}))

    monkeypatch.setattr(trend_draft_job, "run_research", research)
    monkeypatch.setattr(trend_draft_job, "AsyncSessionLocal", pg_session_factory)
    payload = {"org_id": str(m.org), "template_id": template_id}
    await trend_draft_job.handle_trend_draft_job("job-1", payload)
    assert "Priya" not in seen[0]
    async with pg_session_factory() as db:
        row = await db.get(AppraisalRoleTemplate, uuid.UUID(template_id))
    assert row is not None and row.trends_status.value == "draft"
    assert [t["text"] for t in row.trends] == ["Tests are generated"]
    emp = as_user(m.people["emp"], m.org)
    assert (
        await client.post(f"{BASE}/role-templates/{template_id}/trends/draft", headers=emp)
    ).status_code == 403
