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

"""The appraisal tables in real Postgres: constraints, history, audit, merge, keys."""

import base64
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import SecretStr
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.config import settings
from app.core import hr_crypto
from app.models.appraisal import Appraisal
from app.models.appraisal_enums import (
    CheckInCadence,
    FeedbackCadence,
    GoalOrigin,
    GoalRevisionKind,
    GoalStatus,
    ReviewPeriod,
)
from app.models.appraisal_goal import AppraisalGoal
from app.models.appraisal_goal_revision import AppraisalGoalRevision
from app.models.employee_audit_event import EmployeeAuditAction, EmployeeAuditEvent
from app.repositories.employee_sensitive import EmployeeAuditRepository
from app.services.appraisals import audit, crypto
from app.services.employees import hr_key_rotation
from app.services.employees.merge import transfer_employee_record
from app.services.file_storage import FileStorage
from tests.integration.appraisal_support import (
    AppraisalTeam,
    add_and_commit,
    appraisal_team,
    cycle_row,
)
from tests.integration.hr_support import configure_hr_storage
from tests.integration.leave_support import Factory, add_member_without_profile

pytestmark = pytest.mark.integration


@pytest.fixture
def hr_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FileStorage:
    """The shared test HR key (see ``hr_support``)."""
    return configure_hr_storage(monkeypatch, tmp_path)


def _goal(team: AppraisalTeam, position: int | None, status: GoalStatus) -> AppraisalGoal:
    goal = AppraisalGoal(
        org_id=team.org,
        profile_id=team.profile_id,
        cycle_id=team.cycle_id,
        target_period_start=date(2026, 10, 1),
        position=position,
        origin=GoalOrigin.EMPLOYEE_OWN,
        status=status,
    )
    crypto.seal(goal, "title", f"Goal {position}")
    return goal


@pytest.mark.parametrize(
    ("review", "checkins", "feedback"),
    [
        (ReviewPeriod.HALF_YEARLY, CheckInCadence.MONTHLY, FeedbackCadence.IN_REVIEW),
        (ReviewPeriod.QUARTERLY, CheckInCadence.MONTHLY, FeedbackCadence.QUARTERLY),
        (ReviewPeriod.QUARTERLY, CheckInCadence.QUARTERLY, FeedbackCadence.IN_REVIEW),
        (ReviewPeriod.YEARLY, CheckInCadence.QUARTERLY, FeedbackCadence.MONTHLY),
    ],
)
async def test_cycle_rejects_cadences_that_dont_fit(
    pg_session_factory: Factory,
    review: ReviewPeriod,
    checkins: CheckInCadence,
    feedback: FeedbackCadence,
) -> None:
    team = await appraisal_team(pg_session_factory)
    row = cycle_row(
        team.org, review_period=review, checkin_cadence=checkins, feedback_cadence=feedback
    )
    async with pg_session_factory() as db:
        with pytest.raises(IntegrityError, match="ck_appraisal_cycles_"):
            await add_and_commit(db, row)


async def test_cycle_accepts_quarterly_reviews_with_feedback_in_the_review(
    pg_session_factory: Factory,
) -> None:
    team = await appraisal_team(pg_session_factory)
    async with pg_session_factory() as db:
        await add_and_commit(db, cycle_row(team.org, feedback_cadence=FeedbackCadence.IN_REVIEW))


async def test_two_accepted_goals_cannot_share_a_position(
    pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    team = await appraisal_team(pg_session_factory)
    async with pg_session_factory() as db:
        await add_and_commit(db, _goal(team, 1, GoalStatus.ACCEPTED))
        # A dismissed goal may keep a stale position.
        await add_and_commit(db, _goal(team, 1, GoalStatus.DISMISSED))
    async with pg_session_factory() as db:
        with pytest.raises(IntegrityError, match="uq_appraisal_goals_accepted_position"):
            await add_and_commit(db, _goal(team, 1, GoalStatus.ACCEPTED))


async def test_accepted_goal_needs_a_position(
    pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    team = await appraisal_team(pg_session_factory)
    async with pg_session_factory() as db:
        with pytest.raises(IntegrityError, match="ck_appraisal_goals_accepted_position"):
            await add_and_commit(db, _goal(team, None, GoalStatus.ACCEPTED))


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


async def test_goal_history_refuses_delete_and_rewrites(
    pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    team = await appraisal_team(pg_session_factory)
    revision_id = await _revision(pg_session_factory, team)
    for statement in (
        "DELETE FROM appraisal_goal_revisions WHERE id = :id",
        "UPDATE appraisal_goal_revisions SET kind = 'declined' WHERE id = :id",
        "UPDATE appraisal_goal_revisions SET changed_by = gen_random_uuid() WHERE id = :id",
    ):
        async with pg_session_factory() as db:
            with pytest.raises(DBAPIError, match="append-only"):
                await db.execute(text(statement), {"id": revision_id})


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


async def test_views_are_logged_once_a_day_and_never_for_yourself(
    pg_session_factory: Factory,
) -> None:
    team = await appraisal_team(pg_session_factory)
    now = datetime(2026, 11, 4, 9, tzinfo=UTC)
    common = {
        "org_id": team.org,
        "subject_user_id": team.employee,
        "profile_id": team.profile_id,
        "target": team.appraisal_id,
    }
    async with pg_session_factory() as db:
        assert await audit.record_view(db, actor_id=team.manager, now=now, **common)
        await db.commit()
        assert not await audit.record_view(
            db, actor_id=team.manager, now=now + timedelta(hours=8), **common
        )
        assert not await audit.record_view(db, actor_id=team.employee, now=now, **common)
        assert await audit.record_view(
            db, actor_id=team.manager, now=now + timedelta(days=1), **common
        )
        await db.commit()
        rows = (
            await db.execute(
                select(EmployeeAuditEvent).where(
                    EmployeeAuditEvent.target == str(team.appraisal_id)
                )
            )
        ).scalars()
        assert [r.actor_id for r in rows] == [team.manager, team.manager]


async def test_record_access_log_leaves_out_appraisal_events(
    pg_session_factory: Factory,
) -> None:
    team = await appraisal_team(pg_session_factory)
    async with pg_session_factory() as db:
        audit.record(
            db,
            org_id=team.org,
            actor_id=team.manager,
            subject_user_id=team.employee,
            profile_id=team.profile_id,
            action=EmployeeAuditAction.APPRAISAL_SCORED,
            target=team.appraisal_id,
        )
        await db.commit()
        log = await EmployeeAuditRepository(db, org_id=team.org).for_profile(team.profile_id)
        assert log == []


async def test_member_merge_moves_the_scoring_manager(pg_session_factory: Factory) -> None:
    team = await appraisal_team(pg_session_factory)
    stub = await add_member_without_profile(pg_session_factory, team.org, "Ravi (GitHub)")
    async with pg_session_factory() as db:
        appraisal = await db.get(Appraisal, team.appraisal_id)
        assert appraisal is not None
        appraisal.manager_user_id = stub
        await db.commit()
    async with pg_session_factory() as db:
        result = await transfer_employee_record(
            db, org_id=team.org, source=stub, target=team.other
        )
        await db.commit()
        assert result.appraisal_rows_moved == 1
        moved = await db.get(Appraisal, team.appraisal_id)
        assert moved is not None and moved.manager_user_id == team.other


async def test_key_rotation_re_encrypts_appraisal_fields(
    pg_session_factory: Factory, hr_key: FileStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    team = await appraisal_team(pg_session_factory)
    async with pg_session_factory() as db:
        goal = _goal(team, None, GoalStatus.PROPOSED)
        await add_and_commit(db, goal)
    old = settings.hr_crypto.hr_encryption_keys.get_secret_value()
    # The same new key as the employee-record rotation test, so either may
    # run first against the shared database.
    new = base64.b64encode(b"n" * 32).decode()
    monkeypatch.setattr(settings.hr_crypto, "hr_encryption_keys", SecretStr(f"new:{new},{old}"))
    hr_crypto._configured_keyring.cache_clear()
    async with pg_session_factory() as db:
        report = await hr_key_rotation.rotate(db, dry_run=False)
    # Other tests' rows share the database; only this goal's outcome is ours.
    assert not [item for item in report.failed if str(goal.id) in item]
    async with pg_session_factory() as db:
        fresh = await db.get(AppraisalGoal, goal.id)
        assert fresh is not None and fresh.title is not None
        assert hr_crypto.key_id(fresh.title) == "new"
        assert crypto.unseal(fresh, "title") == "Goal None"
