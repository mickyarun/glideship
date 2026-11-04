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

"""The sweeper under stress: crashes, races, leavers, redraft limits, summaries, fairness."""

import json
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.models.appraisal import Appraisal
from app.models.appraisal_ai_run import AppraisalAiRun
from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_enums import DraftKind, DraftStatus, GoalOrigin, GoalStatus
from app.models.appraisal_goal import AppraisalGoal
from app.repositories.appraisal import AppraisalRepository
from app.repositories.appraisal_drafts import claim_next
from app.services.appraisals import crypto, draft_sweeper
from app.services.appraisals.context import MAX_REDRAFTS
from app.services.appraisals.draft_sweeper import STALE_AFTER
from app.services.appraisals.enrolment import withdraw_on_exit
from app.services.claude_errors import ClaudeErrorCode
from app.services.claude_runner import ClaudeRunResult
from app.services.file_storage import FileStorage
from tests.integration.appraisal_month import Month, october
from tests.integration.hr_support import configure_hr_storage
from tests.integration.leave_support import Factory, as_user

pytestmark = pytest.mark.integration
CHECK_INS = "/api/v1/check-ins"


class Model:
    """Stands in for the model; ``calls`` counts every run."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.reply: Any = lambda _p: ClaudeRunResult(success=False, output="", error="x")

    async def __call__(self, _org: uuid.UUID, prompt: str) -> ClaudeRunResult:
        self.calls.append(prompt)
        result = self.reply(prompt)
        return await result if hasattr(result, "__await__") else result


@pytest.fixture
def hr_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FileStorage:
    """The shared test HR key (see ``hr_support``)."""
    return configure_hr_storage(monkeypatch, tmp_path)


@pytest.fixture
async def model(monkeypatch: pytest.MonkeyPatch, pg_session_factory: Factory) -> Model:
    """A stand-in model, with other tests' waiting drafts cleared out of its way."""
    stand_in = Model()
    monkeypatch.setattr(draft_sweeper, "AsyncSessionLocal", pg_session_factory)
    monkeypatch.setattr(draft_sweeper, "run_draft", stand_in)
    async with pg_session_factory() as db:
        for table, column in (
            (AppraisalCheckIn, AppraisalCheckIn.draft_status),
            (Appraisal, Appraisal.period_summary_status),
        ):
            await db.execute(
                update(table).where(column == DraftStatus.PENDING).values({column.key: "none"})
            )
        await db.commit()
    return stand_in


def _good(ids: list[str], section: str = "team") -> ClaudeRunResult:
    lines = [{"section": section, "text": "Covered support", "fact_ids": ids}]
    return ClaudeRunResult(success=True, output=json.dumps({"lines": lines}))


async def _row(factory: Factory, m: Month) -> AppraisalCheckIn:
    async with factory() as db:
        rows = await db.scalars(select(AppraisalCheckIn).where(AppraisalCheckIn.org_id == m.org))
        return next(r for r in rows if r.fact_refs)


async def test_a_manual_cycle_never_reaches_the_model(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage, model: Model
) -> None:
    m = await october(client, pg_session_factory)
    row = await _row(pg_session_factory, m)
    me = as_user(m.people["emp"], m.org)
    await client.put(f"{CHECK_INS}/{row.id}/note", json={"blocking": "x"}, headers=me)
    async with pg_session_factory() as db:
        assert await AppraisalRepository(db, org_id=m.org).queue_summaries(row.cycle_id) == 0
    await draft_sweeper.tick_once()
    assert model.calls == []


async def test_a_note_saved_during_a_run_survives_it(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage, model: Model
) -> None:
    m = await october(client, pg_session_factory, ai=True)
    row = await _row(pg_session_factory, m)
    me = as_user(m.people["emp"], m.org)

    async def mid_run(_prompt: str) -> ClaudeRunResult:
        saved = await client.put(
            f"{CHECK_INS}/{row.id}/note", json={"blocking": "Late"}, headers=me
        )
        assert saved.status_code == 200
        return _good([str(m.counted)])

    model.reply = mid_run
    await draft_sweeper.tick_once()
    read = (await client.get(f"{CHECK_INS}/{row.id}", headers=me)).json()
    assert read["note"]["blocking"] == "Late" and read["ai_lines"]


async def test_a_claim_is_only_retaken_once_stale(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage, model: Model
) -> None:
    m = await october(client, pg_session_factory, ai=True)
    now = datetime.now(UTC)
    async with pg_session_factory() as db:
        await db.execute(
            update(AppraisalCheckIn)
            .where(AppraisalCheckIn.org_id == m.org)
            .values(draft_claimed_at=now - STALE_AFTER + timedelta(minutes=1))
        )
        await db.commit()
    await draft_sweeper.tick_once(now)
    assert model.calls == []
    model.reply = lambda _p: _good([str(m.counted)])
    await draft_sweeper.tick_once(now + timedelta(minutes=2))
    assert len(model.calls) == 1


async def test_crashes_stop_at_the_attempt_limit(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage, model: Model
) -> None:
    m = await october(client, pg_session_factory, ai=True)

    def boom(_prompt: str) -> ClaudeRunResult:
        raise RuntimeError("process died")

    model.reply = boom
    start = datetime.now(UTC)
    for i in range(5):
        await draft_sweeper.tick_once(start + i * (STALE_AFTER + timedelta(minutes=1)))
    row = await _row(pg_session_factory, m)
    assert len(model.calls) == 3
    assert (row.draft_status, row.draft_error) == (DraftStatus.FAILED, "crashed")


async def test_two_sweepers_never_share_a_row(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage, model: Model
) -> None:
    await october(client, pg_session_factory, ai=True)
    now = datetime.now(UTC)
    columns = (AppraisalCheckIn.draft_status, AppraisalCheckIn.draft_claimed_at, "draft_attempts")
    stale = now - STALE_AFTER
    async with pg_session_factory() as first, pg_session_factory() as second:
        one = await claim_next(first, AppraisalCheckIn, columns, now, stale, ())
        two = await claim_next(second, AppraisalCheckIn, columns, now, stale, ())
        assert one is not None and two is not None and one.record_id != two.record_id
        await first.rollback()
        await second.rollback()


async def test_orgs_take_turns(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage, model: Model
) -> None:
    older = await october(client, pg_session_factory, ai=True)
    newer = await october(client, pg_session_factory, ai=True)
    now = datetime.now(UTC)
    columns = (AppraisalCheckIn.draft_status, AppraisalCheckIn.draft_claimed_at, "draft_attempts")
    async with pg_session_factory() as db:
        first = await claim_next(db, AppraisalCheckIn, columns, now, now, ())
        assert first is not None and first.org_id == older.org
        second = await claim_next(db, AppraisalCheckIn, columns, now, now, {older.org})
        assert second is not None and second.org_id == newer.org
        await db.rollback()


async def test_a_result_for_a_cancelled_draft_is_dropped(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage, model: Model
) -> None:
    m = await october(client, pg_session_factory, ai=True)
    row = await _row(pg_session_factory, m)

    async def leaves_mid_run(_prompt: str) -> ClaudeRunResult:
        async with pg_session_factory() as db:
            await withdraw_on_exit(db, m.org, row.profile_id)
            await db.commit()
        return _good([str(m.counted)])

    model.reply = leaves_mid_run
    await draft_sweeper.tick_once()
    fresh = await _row(pg_session_factory, m)
    assert fresh.draft_status is DraftStatus.NONE and fresh.ai_summary is None


async def test_withdrawing_stops_waiting_drafts(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage, model: Model
) -> None:
    m = await october(client, pg_session_factory, ai=True)
    row = await _row(pg_session_factory, m)
    async with pg_session_factory() as db:
        await withdraw_on_exit(db, m.org, row.profile_id)
        await db.commit()
    model.reply = lambda _p: _good([str(m.counted)])
    await draft_sweeper.tick_once()
    # Meena's check-in has no facts, so nothing at all reached the model.
    assert model.calls == []


async def test_redrafts_are_limited_and_keep_the_old_lines_meanwhile(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage, model: Model
) -> None:
    m = await october(client, pg_session_factory, ai=True)
    row = await _row(pg_session_factory, m)
    url = f"{CHECK_INS}/{row.id}"
    manager = as_user(m.people["mgr"], m.org)
    model.reply = lambda _p: _good([str(m.counted)])
    await draft_sweeper.tick_once()
    me = as_user(m.people["emp"], m.org)
    for _ in range(MAX_REDRAFTS):
        asked = await client.post(f"{url}/regenerate", headers=me)
        assert asked.status_code == 202 and asked.json()["ai_lines"]
        await draft_sweeper.tick_once()
    assert (await client.post(f"{url}/regenerate", headers=me)).status_code == 409
    assert (await client.post(f"{url}/regenerate", headers=manager)).status_code == 409


async def test_a_manager_may_redraft_but_hr_may_not(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage, model: Model
) -> None:
    m = await october(client, pg_session_factory, ai=True)
    row = await _row(pg_session_factory, m)
    url = f"{CHECK_INS}/{row.id}/regenerate"
    model.reply = lambda _p: _good([str(m.counted)])
    await draft_sweeper.tick_once()
    assert (await client.post(url, headers=as_user(m.people["hr"], m.org))).status_code == 409
    assert (await client.post(url, headers=as_user(m.people["mgr"], m.org))).status_code == 202


@pytest.mark.parametrize(
    ("code", "tries", "status"),
    [
        (ClaudeErrorCode.TIMEOUT, 3, DraftStatus.FAILED),
        (ClaudeErrorCode.AUTH, 1, DraftStatus.NONE),
    ],
)
async def test_summaries_follow_the_same_retry_rules(
    client: AsyncClient,
    pg_session_factory: Factory,
    hr_key: FileStorage,
    model: Model,
    code: ClaudeErrorCode,
    tries: int,
    status: DraftStatus,
) -> None:
    m = await october(client, pg_session_factory, ai=True)
    row = await _row(pg_session_factory, m)
    model.reply = lambda _p: _good([str(m.counted)])
    await draft_sweeper.tick_once()
    async with pg_session_factory() as db:
        await AppraisalRepository(db, org_id=m.org).queue_summaries(row.cycle_id)
        await db.commit()
    model.reply = lambda _p: ClaudeRunResult(success=False, output="", error="x", error_code=code)
    start = datetime.now(UTC)
    for i in range(tries):
        await draft_sweeper.tick_once(start + i * (STALE_AFTER + timedelta(minutes=1)))
    async with pg_session_factory() as db:
        appraisal = await db.scalar(
            select(Appraisal).where(
                Appraisal.profile_id == row.profile_id, Appraisal.cycle_id == row.cycle_id
            )
        )
        assert appraisal is not None
        runs = await db.scalars(
            select(AppraisalAiRun).where(
                AppraisalAiRun.record_id == appraisal.id,
                AppraisalAiRun.kind == DraftKind.PERIOD_SUMMARY,
            )
        )
        assert len(list(runs)) == tries
    assert appraisal.period_summary_status is status
    assert appraisal.summary_error == code.value


async def test_summary_sections_for_this_periods_goals_only(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage, model: Model
) -> None:
    m = await october(client, pg_session_factory, ai=True)
    row = await _row(pg_session_factory, m)
    model.reply = lambda _p: _good([str(m.counted)])
    await draft_sweeper.tick_once()
    async with pg_session_factory() as db:
        goal = AppraisalGoal(
            org_id=m.org,
            profile_id=row.profile_id,
            cycle_id=row.cycle_id,
            target_period_start=date(2026, 10, 1),
            position=1,
            origin=GoalOrigin.EMPLOYEE_OWN,
            status=GoalStatus.ACCEPTED,
        )
        crypto.seal(goal, "title", "Close in 5 days")
        db.add(goal)
        await AppraisalRepository(db, org_id=m.org).queue_summaries(row.cycle_id)
        await db.commit()

    def reply(_prompt: str) -> ClaudeRunResult:
        lines = [
            {
                "section": f"goal:{goal.id}",
                "text": "Fixed the close",
                "fact_ids": [str(m.counted)],
            },
            {"section": f"goal:{uuid.uuid4()}", "text": "Other", "fact_ids": [str(m.counted)]},
        ]
        return ClaudeRunResult(success=True, output=json.dumps({"lines": lines}))

    model.reply = reply
    await draft_sweeper.tick_once()
    async with pg_session_factory() as db:
        appraisal = await db.scalar(
            select(Appraisal).where(
                Appraisal.profile_id == row.profile_id, Appraisal.cycle_id == row.cycle_id
            )
        )
        assert appraisal is not None
        saved = crypto.unseal_json(appraisal, "ai_period_summary")
    assert [line["section"] for line in saved] == [f"goal:{goal.id}"]
