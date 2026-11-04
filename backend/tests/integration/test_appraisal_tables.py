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

"""Appraisal goal history, audit entries, member merges and key rotation."""

import base64
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import SecretStr
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.config import settings
from app.core import hr_crypto
from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import GoalOrigin, GoalRevisionKind, GoalStatus
from app.models.appraisal_goal import AppraisalGoal
from app.models.appraisal_goal_revision import AppraisalGoalRevision
from app.models.employee_audit_event import EmployeeAuditAction, EmployeeAuditEvent
from app.repositories.employee_sensitive import EmployeeAuditRepository
from app.services.appraisals import audit, crypto
from app.services.employees import hr_key_rotation
from app.services.file_storage import FileStorage
from tests.integration.appraisal_support import (
    AppraisalTeam,
    add_and_commit,
    appraisal_team,
)
from tests.integration.hr_support import configure_hr_storage
from tests.integration.leave_support import Factory

pytestmark = pytest.mark.integration


@pytest.fixture
def hr_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FileStorage:
    """The shared test HR key (see ``hr_support``)."""
    return configure_hr_storage(monkeypatch, tmp_path)


def _goal(team: AppraisalTeam) -> AppraisalGoal:
    goal = AppraisalGoal(
        org_id=team.org,
        profile_id=team.profile_id,
        cycle_id=team.cycle_id,
        target_period_start=date(2026, 10, 1),
        origin=GoalOrigin.EMPLOYEE_OWN,
        status=GoalStatus.PROPOSED,
    )
    crypto.seal(goal, "title", "Cut nightly setup failures")
    return goal


async def _revision(factory: Factory, team: AppraisalTeam) -> uuid.UUID:
    async with factory() as db:
        revision = AppraisalGoalRevision(
            org_id=team.org,
            goal_id=uuid.uuid4(),
            changed_by=team.manager,
            kind=GoalRevisionKind.EDITED,
        )
        crypto.seal(revision, "reason", "Scope changed")
        await add_and_commit(db, revision)
        return revision.id


@pytest.mark.parametrize(
    "statement",
    [
        "DELETE FROM appraisal_goal_revisions WHERE id = :id",
        "UPDATE appraisal_goal_revisions SET kind = 'declined' WHERE id = :id",
        "UPDATE appraisal_goal_revisions SET changed_by = gen_random_uuid() WHERE id = :id",
        "UPDATE appraisal_goal_revisions SET goal_id = gen_random_uuid() WHERE id = :id",
        "UPDATE appraisal_goal_revisions SET created_at = now() - interval '1 day' WHERE id = :id",
        "UPDATE appraisal_goal_revisions SET reason = NULL WHERE id = :id",
        "UPDATE appraisal_goal_revisions SET before = '\\x00'::bytea WHERE id = :id",
    ],
)
async def test_goal_history_refuses_deletes_and_rewrites(
    pg_session_factory: Factory, hr_key: FileStorage, statement: str
) -> None:
    team = await appraisal_team(pg_session_factory)
    revision_id = await _revision(pg_session_factory, team)
    async with pg_session_factory() as db:
        with pytest.raises(DBAPIError, match="append-only"):
            await db.execute(text(statement), {"id": revision_id})


async def test_goal_history_refuses_truncate(pg_session_factory: Factory) -> None:
    async with pg_session_factory() as db:
        with pytest.raises(DBAPIError, match="append-only"):
            await db.execute(text("TRUNCATE appraisal_goal_revisions"))


async def test_goal_history_allows_re_encrypting(
    pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    team = await appraisal_team(pg_session_factory)
    revision_id = await _revision(pg_session_factory, team)
    async with pg_session_factory() as db:
        revision = await db.get(AppraisalGoalRevision, revision_id)
        assert revision is not None
        crypto.seal(revision, "reason", "Scope changed")
        await db.commit()


async def test_goal_history_purge_needs_the_explicit_setting(
    pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    team = await appraisal_team(pg_session_factory)
    revision_id = await _revision(pg_session_factory, team)
    async with pg_session_factory() as db:
        await db.execute(text("SET LOCAL glideship.purge_goal_history = 'on'"))
        await db.execute(
            text("DELETE FROM appraisal_goal_revisions WHERE id = :id"), {"id": revision_id}
        )
        await db.commit()
        assert await db.get(AppraisalGoalRevision, revision_id) is None


async def test_views_are_logged_once_a_day_and_never_for_yourself(
    pg_session_factory: Factory,
) -> None:
    team = await appraisal_team(pg_session_factory)
    # Any date works: the entry carries the same clock the check uses.
    now = datetime(2025, 3, 2, 9, tzinfo=UTC)
    common = {
        "org_id": team.org,
        "subject_user_id": team.employee,
        "profile_id": team.profile_id,
        "target": team.appraisal_id,
    }
    async with pg_session_factory() as db:
        assert await audit.record_view(db, actor_id=team.manager, now=now, **common)
        await db.flush()
        later = now + timedelta(hours=8)
        assert not await audit.record_view(db, actor_id=team.manager, now=later, **common)
        assert not await audit.record_view(db, actor_id=team.employee, now=now, **common)
        tomorrow = now + timedelta(days=1)
        assert await audit.record_view(db, actor_id=team.manager, now=tomorrow, **common)
        await db.commit()
        rows = (
            await db.execute(
                select(EmployeeAuditEvent.created_at).where(
                    EmployeeAuditEvent.target == str(team.appraisal_id)
                )
            )
        ).scalars()
        assert sorted(rows) == [now, tomorrow]


async def test_record_access_log_leaves_out_appraisal_events(
    pg_session_factory: Factory,
) -> None:
    team = await appraisal_team(pg_session_factory)
    async with pg_session_factory() as db:
        for action in (EmployeeAuditAction.APPRAISAL_SCORED, EmployeeAuditAction.FIELD_REVEALED):
            audit.record(
                db,
                org_id=team.org,
                actor_id=team.manager,
                subject_user_id=team.employee,
                profile_id=team.profile_id,
                action=action,
                target=team.appraisal_id,
            )
        await db.commit()
        log = await EmployeeAuditRepository(db, org_id=team.org).for_profile(team.profile_id)
        assert [e.action for e in log] == [EmployeeAuditAction.FIELD_REVEALED]


async def test_key_rotation_re_encrypts_every_kind_of_appraisal_row(
    pg_session_factory: Factory, hr_key: FileStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    team = await appraisal_team(pg_session_factory)
    revision_id = await _revision(pg_session_factory, team)
    async with pg_session_factory() as db:
        goal = _goal(team)
        db.add(goal)
        cycle = await db.get(AppraisalCycle, team.cycle_id)
        assert cycle is not None
        crypto.seal(cycle, "intro_note", "Welcome to Q4")
        check_in = AppraisalCheckIn(
            org_id=team.org,
            profile_id=team.profile_id,
            cycle_id=team.cycle_id,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 31),
            working_days=22,
            available_days=22,
        )
        crypto.seal_json(check_in, "employee_note", {"growth": ["Learned Terraform"]})
        await add_and_commit(db, check_in)
    old = settings.hr_crypto.hr_encryption_keys.get_secret_value()
    # The same new key as the employee-record rotation test, so either may
    # run first against the shared database.
    new = base64.b64encode(b"n" * 32).decode()
    monkeypatch.setattr(settings.hr_crypto, "hr_encryption_keys", SecretStr(f"new:{new},{old}"))
    hr_crypto._configured_keyring.cache_clear()
    async with pg_session_factory() as db:
        report = await hr_key_rotation.rotate(db, dry_run=False)
    ours = {str(goal.id), str(cycle.id), str(check_in.id), str(revision_id)}
    assert not [item for item in report.failed if any(i in item for i in ours)]
    async with pg_session_factory() as db:
        rows = [
            (await db.get(AppraisalGoal, goal.id), "title", "Cut nightly setup failures"),
            (await db.get(AppraisalCycle, cycle.id), "intro_note", "Welcome to Q4"),
            (await db.get(AppraisalGoalRevision, revision_id), "reason", "Scope changed"),
        ]
        for row, field, plain in rows:
            assert row is not None
            assert hr_crypto.key_id(getattr(row, field)) == "new"
            assert crypto.unseal(row, field) == plain
        fresh = await db.get(AppraisalCheckIn, check_in.id)
        assert fresh is not None
        assert crypto.unseal_json(fresh, "employee_note") == {"growth": ["Learned Terraform"]}
