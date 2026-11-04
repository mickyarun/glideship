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

"""AI drafts end to end with a stand-in model: sweeper, retries, hiding, regenerate."""

import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.appraisal import Appraisal
from app.models.appraisal_ai_run import AppraisalAiRun
from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_enums import DraftStatus
from app.models.organization import Organization
from app.repositories.appraisal import AppraisalRepository
from app.services.appraisals import crypto, draft_sweeper
from app.services.appraisals.draft_sweeper import STALE_AFTER
from app.services.appraisals.settings import CONFIG_KEY
from app.services.claude_errors import ClaudeErrorCode
from app.services.claude_runner import ClaudeRunResult
from app.services.file_storage import FileStorage
from tests.integration.appraisal_month import Month, october
from tests.integration.hr_support import configure_hr_storage
from tests.integration.leave_support import Factory, as_user

pytestmark = pytest.mark.integration
CHECK_INS = "/api/v1/check-ins"
Reply = Callable[[str], ClaudeRunResult]
RETRY_WAIT = STALE_AFTER + timedelta(minutes=1)


@pytest.fixture
def hr_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FileStorage:
    """The shared test HR key (see ``hr_support``)."""
    return configure_hr_storage(monkeypatch, tmp_path)


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch, pg_session_factory: Factory) -> list[Reply]:
    """Stands in for the model; push a reply, and each run uses the latest one."""
    replies: list[Reply] = []
    monkeypatch.setattr(draft_sweeper, "AsyncSessionLocal", pg_session_factory)

    async def run(_org: uuid.UUID, prompt: str) -> ClaudeRunResult:
        return replies[-1](prompt)

    monkeypatch.setattr(draft_sweeper, "run_draft", run)
    return replies


def _cite(ids: list[str]) -> Reply:
    lines = [
        {"section": "delivery_quality", "text": "Renewed the vendor contract", "fact_ids": ids},
        {"section": "team", "text": "Made up with no citation", "fact_ids": []},
    ]
    return lambda _prompt: ClaudeRunResult(success=True, output=json.dumps({"lines": lines}))


def _fails(code: ClaudeErrorCode) -> Reply:
    return lambda _prompt: ClaudeRunResult(success=False, output="", error="x", error_code=code)


async def _row(factory: Factory, m: Month) -> AppraisalCheckIn:
    async with factory() as db:
        rows = list(
            await db.scalars(select(AppraisalCheckIn).where(AppraisalCheckIn.org_id == m.org))
        )
    return next(r for r in rows if r.fact_refs)


async def _sweep(factory: Factory, m: Month, later: int = 0) -> AppraisalCheckIn:
    """A sweeper pass ``later`` retry waits from now, and this org's check-in after it."""
    await draft_sweeper.tick_once(datetime.now(UTC) + later * RETRY_WAIT)
    return await _row(factory, m)


async def test_a_draft_keeps_cited_lines_and_records_the_run(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage, model: list[Reply]
) -> None:
    m = await october(client, pg_session_factory, ai=True)
    model.append(_cite([str(m.counted)]))
    row = await _sweep(pg_session_factory, m)
    assert row.draft_status is DraftStatus.READY and row.ai_generated_at is not None
    me = as_user(m.people["emp"], m.org)
    read = (await client.get(f"{CHECK_INS}/{row.id}", headers=me)).json()
    assert [line["text"] for line in read["ai_lines"]] == ["Renewed the vendor contract"]
    async with pg_session_factory() as db:
        run = await db.scalar(select(AppraisalAiRun).where(AppraisalAiRun.record_id == row.id))
        assert run is not None and run.error is None
        assert str(m.counted) in run.fact_ids
        prompt = crypto.unseal(run, "prompt") or ""
    assert "Priya" not in prompt and "Renew the payroll vendor contract" in prompt


async def test_retries_three_times_then_fails_and_the_check_in_still_works(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage, model: list[Reply]
) -> None:
    m = await october(client, pg_session_factory, ai=True)
    model.append(_fails(ClaudeErrorCode.TIMEOUT))
    row = await _sweep(pg_session_factory, m)
    # It keeps its claim, so the next try waits.
    assert row.draft_status is DraftStatus.PENDING and row.draft_claimed_at is not None
    assert (await _sweep(pg_session_factory, m)).draft_attempts == 1
    await _sweep(pg_session_factory, m, later=1)
    row = await _sweep(pg_session_factory, m, later=2)
    assert row.draft_status is DraftStatus.FAILED and row.draft_error == "timeout"
    assert row.draft_attempts == 3
    me = as_user(m.people["emp"], m.org)
    read = (await client.get(f"{CHECK_INS}/{row.id}", headers=me)).json()
    assert read["facts"] and read["ai_lines"] == [] and read["can_regenerate"]
    saved = await client.put(f"{CHECK_INS}/{row.id}/note", json={"blocking": "x"}, headers=me)
    assert saved.status_code == 200


@pytest.mark.parametrize(
    "code", [ClaudeErrorCode.UNSUPPORTED, ClaudeErrorCode.BINARY_MISSING, ClaudeErrorCode.AUTH]
)
async def test_permanent_errors_go_straight_to_manual(
    client: AsyncClient,
    pg_session_factory: Factory,
    hr_key: FileStorage,
    model: list[Reply],
    code: ClaudeErrorCode,
) -> None:
    m = await october(client, pg_session_factory, ai=True)
    model.append(_fails(code))
    row = await _sweep(pg_session_factory, m)
    assert row.draft_status is DraftStatus.NONE and row.draft_attempts == 1


async def test_unreadable_output_and_no_cited_lines_are_retried(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage, model: list[Reply]
) -> None:
    m = await october(client, pg_session_factory, ai=True)
    model.append(lambda _p: ClaudeRunResult(success=True, output="Sorry, no."))
    row = await _sweep(pg_session_factory, m)
    assert (row.draft_status, row.draft_error) == (DraftStatus.PENDING, "unreadable")
    model.append(_cite(["made-up-id"]))
    row = await _sweep(pg_session_factory, m, later=1)
    assert (row.draft_status, row.draft_error) == (DraftStatus.PENDING, "no_cited_lines")


async def test_turning_ai_off_stops_the_draft_without_a_run(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage, model: list[Reply]
) -> None:
    m = await october(client, pg_session_factory, ai=True)
    async with pg_session_factory() as db:
        org = await db.get(Organization, m.org)
        assert org is not None
        org.config = {**(org.config or {}), CONFIG_KEY: {"ai_enabled": False}}
        await db.commit()
    model.append(_fails(ClaudeErrorCode.TIMEOUT))
    row = await _sweep(pg_session_factory, m)
    assert row.draft_status is DraftStatus.NONE
    async with pg_session_factory() as db:
        # The sweeper is global, so other tests' rows may run; this one must not.
        runs = await db.scalars(select(AppraisalAiRun).where(AppraisalAiRun.record_id == row.id))
        assert list(runs) == []


async def test_a_late_draft_leaves_what_the_person_wrote(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage, model: list[Reply]
) -> None:
    m = await october(client, pg_session_factory, ai=True)
    row = await _row(pg_session_factory, m)
    me = as_user(m.people["emp"], m.org)
    await client.put(f"{CHECK_INS}/{row.id}/note", json={"blocking": "Access"}, headers=me)
    model.append(_cite([str(m.counted)]))
    await _sweep(pg_session_factory, m)
    read = (await client.get(f"{CHECK_INS}/{row.id}", headers=me)).json()
    assert read["note"]["blocking"] == "Access" and read["ai_lines"]


async def test_someone_who_cant_open_a_fact_doesnt_get_the_summary(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage, model: list[Reply]
) -> None:
    m = await october(client, pg_session_factory, ai=True)
    model.append(_cite([str(m.counted)]))
    row = await _sweep(pg_session_factory, m)
    # The card is on a members-only board the manager isn't on.
    read = (
        await client.get(f"{CHECK_INS}/{row.id}", headers=as_user(m.people["mgr"], m.org))
    ).json()
    assert read["ai_lines"] == [] and read["ai_hidden"] is True


async def test_regenerate_rules(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage, model: list[Reply]
) -> None:
    m = await october(client, pg_session_factory, ai=True)
    model.append(_cite([str(m.counted)]))
    row = await _sweep(pg_session_factory, m)
    url = f"{CHECK_INS}/{row.id}"
    stranger = as_user(m.people["stranger"], m.org)
    assert (await client.post(f"{url}/regenerate", headers=stranger)).status_code == 404
    me = as_user(m.people["emp"], m.org)
    asked = await client.post(f"{url}/regenerate", headers=me)
    assert asked.status_code == 202 and asked.json()["draft_status"] == "pending"
    assert (await client.post(f"{url}/regenerate", headers=me)).status_code == 409
    await _sweep(pg_session_factory, m)
    await client.put(f"{url}/note", json={"blocking": "Access"}, headers=me)
    assert (await client.post(f"{url}/regenerate", headers=me)).status_code == 409


async def test_manual_check_ins_cant_be_regenerated(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    m = await october(client, pg_session_factory)
    row = await _row(pg_session_factory, m)
    me = as_user(m.people["emp"], m.org)
    assert (await client.post(f"{CHECK_INS}/{row.id}/regenerate", headers=me)).status_code == 409


async def test_period_summary_cites_months_and_facts(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage, model: list[Reply]
) -> None:
    m = await october(client, pg_session_factory, ai=True)
    model.append(_cite([str(m.counted)]))
    row = await _sweep(pg_session_factory, m)
    me = as_user(m.people["emp"], m.org)
    await client.put(f"{CHECK_INS}/{row.id}/note", json={"blocking": "Access logs"}, headers=me)
    async with pg_session_factory() as db:
        queued = await AppraisalRepository(db, org_id=m.org).queue_summaries(row.cycle_id)
        await db.commit()
    assert queued == 2
    prompts: list[str] = []

    def reply(prompt: str) -> ClaudeRunResult:
        prompts.append(prompt)
        lines = [
            {
                "section": "blockers",
                "text": "Access logs held things up",
                "fact_ids": [str(row.id)],
            }
        ]
        return ClaudeRunResult(success=True, output=json.dumps({"lines": lines}))

    model.append(reply)
    await draft_sweeper.tick_once(datetime.now(UTC))
    async with pg_session_factory() as db:
        appraisal = await db.scalar(
            select(Appraisal).where(
                Appraisal.profile_id == row.profile_id, Appraisal.cycle_id == row.cycle_id
            )
        )
        assert appraisal is not None
        assert appraisal.period_summary_status is DraftStatus.READY
        saved = crypto.unseal_json(appraisal, "ai_period_summary")
    assert saved[0]["text"] == "Access logs held things up"
    assert any(f'"check_in": "{row.id}"' in p and "Access logs" in p for p in prompts)
