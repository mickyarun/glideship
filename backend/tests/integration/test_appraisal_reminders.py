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

"""Appraisal reminder DMs: what goes to whom on which day, once, and only with Slack."""

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_manager_feedback import AppraisalManagerFeedback
from app.models.digest_claim import DigestClaim, DigestClaimKind, DigestClaimStatus
from app.repositories.appraisal_cycle import CycleOrg, orgs_with_running_cycles
from app.services.appraisals import reminder_job
from app.services.file_storage import FileStorage
from tests.integration.appraisal_month import NOV_2, Month, october
from tests.integration.board_notify_support import Slack, fake_slack, link_slack, mute
from tests.integration.hr_support import configure_hr_storage
from tests.integration.leave_support import Factory, as_user

pytestmark = pytest.mark.integration
FEEDBACK = "/api/v1/manager-feedback"


def at(day: int, hour: int = 10, minute: int = 30) -> datetime:
    """A moment in November 2026, UTC (the test org's clock)."""
    return datetime(2026, 11, day, hour, minute, tzinfo=UTC)


@pytest.fixture
def hr_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FileStorage:
    """The shared test HR key (see ``hr_support``)."""
    return configure_hr_storage(monkeypatch, tmp_path)


@pytest.fixture
def slack(monkeypatch: pytest.MonkeyPatch, pg_session_factory: Factory) -> Slack:
    monkeypatch.setattr(reminder_job, "AsyncSessionLocal", pg_session_factory)
    return fake_slack(monkeypatch, pg_session_factory)


async def _month(client: AsyncClient, factory: Factory) -> tuple[Month, dict[str, str]]:
    """October, with everything opened on 2 November and everyone on Slack."""
    m = await october(client, factory)
    async with factory() as db:
        for model in (AppraisalCheckIn, AppraisalManagerFeedback):
            await db.execute(update(model).where(model.org_id == m.org).values(created_at=NOV_2))
        await db.commit()
    people = ("hr", "mgr", "emp", "quiet")
    ids = await link_slack(factory, m.org, *(m.people[p] for p in people))
    return m, {p: ids[m.people[p]] for p in people}


async def _org(factory: Factory, org: uuid.UUID) -> CycleOrg:
    async with factory() as db:
        return next(o for o in await orgs_with_running_cycles(db) if o.org_id == org)


async def _sent(slack: Slack, org: CycleOrg, now: datetime) -> dict[str, str]:
    """Run one reminder pass; the DMs it posted, by Slack id."""
    slack.posts.clear()
    await reminder_job.org_pass(org, now)
    return dict(await slack.flush())


async def test_opening_day_tells_people_and_the_manager_once(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage, slack: Slack
) -> None:
    m, ids = await _month(client, pg_session_factory)
    org = await _org(pg_session_factory, m.org)
    assert await _sent(slack, org, at(2, 9)) == {}  # before the send time
    sent = await _sent(slack, org, at(2))
    assert set(sent) == {ids["emp"], ids["quiet"], ids["mgr"]}
    assert sent[ids["emp"]].startswith("Your October check-in is ready.")
    assert sent[ids["mgr"]].startswith(
        "October feedback is open for your 2 reports. Due Tue 10 Nov."
    )
    assert "Priya" not in sent[ids["mgr"]] and "Meena" not in sent[ids["mgr"]]
    assert await _sent(slack, org, at(2, 11)) == {}
    async with pg_session_factory() as db:
        claims = list(await db.scalars(select(DigestClaim).where(DigestClaim.org_id == m.org)))
    assert {c.status for c in claims} == {DigestClaimStatus.SENT}
    assert {c.kind for c in claims} == {
        DigestClaimKind.APPRAISAL_CHECK_IN_READY,
        DigestClaimKind.APPRAISAL_FEEDBACK_DUE,
    }


async def test_the_manager_is_reminded_on_the_schedule_and_hr_gets_the_list(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage, slack: Slack
) -> None:
    m, ids = await _month(client, pg_session_factory)
    org = await _org(pg_session_factory, m.org)
    before = await _sent(slack, org, at(5))
    assert before == {ids["mgr"]: before[ids["mgr"]]}
    assert before[ids["mgr"]].startswith("October feedback due Tue 10 Nov: 0 of 2 done.")
    assert await _sent(slack, org, at(6)) == {}
    async with pg_session_factory() as db:
        item = (
            await db.scalars(
                select(AppraisalManagerFeedback).where(AppraisalManagerFeedback.org_id == m.org)
            )
        ).first()
        assert item is not None
    mgr = as_user(m.people["mgr"], m.org)
    url = f"{FEEDBACK}/{item.id}"
    await client.put(url, json={"keep": "Clear PRs", "try_next": "Pair on UAT"}, headers=mgr)
    assert (await client.post(f"{url}/done", headers=mgr)).status_code == 200
    due = await _sent(slack, org, at(10))
    assert due[ids["mgr"]].startswith("October feedback is due today: 1 of 2 done.")
    late = await _sent(slack, org, at(12))
    assert late[ids["mgr"]].startswith("October feedback was due Tue 10 Nov: 1 of 2 done.")
    hr_day = await _sent(slack, org, at(13))
    assert set(hr_day) == {ids["hr"]}
    assert hr_day[ids["hr"]].startswith("Manager feedback still open past its due date: Ravi 1.")


async def test_nothing_once_everything_is_done(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage, slack: Slack
) -> None:
    m, ids = await _month(client, pg_session_factory)
    org = await _org(pg_session_factory, m.org)
    mgr = as_user(m.people["mgr"], m.org)
    for row in (await client.get(f"{FEEDBACK}/team", headers=mgr)).json():
        url = f"{FEEDBACK}/{row['id']}"
        await client.put(url, json={"keep": "a", "try_next": "b"}, headers=mgr)
        await client.post(f"{url}/done", headers=mgr)
    for day in (5, 10, 12, 13):
        assert await _sent(slack, org, at(day)) == {}, day


async def test_a_muted_manager_still_appears_on_hrs_list(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage, slack: Slack
) -> None:
    m, ids = await _month(client, pg_session_factory)
    await mute(pg_session_factory, m.people["mgr"], "appraisal_reminders")
    org = await _org(pg_session_factory, m.org)
    assert ids["mgr"] not in await _sent(slack, org, at(5))
    hr_day = await _sent(slack, org, at(13))
    assert hr_day[ids["hr"]].startswith("Manager feedback still open past its due date: Ravi 2.")
    async with pg_session_factory() as db:
        claim = await db.scalar(
            select(DigestClaim).where(
                DigestClaim.org_id == m.org,
                DigestClaim.user_id == m.people["mgr"],
                DigestClaim.kind == DigestClaimKind.APPRAISAL_FEEDBACK_DUE,
            )
        )
    assert claim is not None and claim.status is DigestClaimStatus.SKIPPED


async def test_no_slack_means_no_claims(
    client: AsyncClient, pg_session_factory: Factory, hr_key: FileStorage, slack: Slack
) -> None:
    m = await october(client, pg_session_factory)
    org = await _org(pg_session_factory, m.org)
    assert await _sent(slack, org, at(2)) == {}
    async with pg_session_factory() as db:
        assert (
            await db.scalars(select(DigestClaim).where(DigestClaim.org_id == m.org))
        ).all() == []
