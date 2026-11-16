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

"""Member merges carry every appraisal user id across, within one org only."""

import uuid
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import func, select, update

from app.models.appraisal import Appraisal
from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import (
    CheckInCadence,
    EvidenceHeading,
    GoalOrigin,
    GoalRevisionKind,
    GoalStatus,
)
from app.models.appraisal_evidence_link import AppraisalEvidenceLink
from app.models.appraisal_goal import AppraisalGoal
from app.models.appraisal_goal_revision import AppraisalGoalRevision
from app.models.appraisal_goal_value import AppraisalGoalValue
from app.models.appraisal_manager_feedback import AppraisalManagerFeedback
from app.models.appraisal_role_template import AppraisalRoleTemplate
from app.repositories.appraisal_merge import USER_COLUMNS
from app.services.appraisals import crypto
from app.services.employees.merge import EmployeeMergeConflictError, transfer_employee_record
from app.services.file_storage import FileStorage
from tests.integration.appraisal_support import AppraisalTeam, appraisal_team
from tests.integration.hr_support import configure_hr_storage
from tests.integration.leave_support import Factory, add_member_without_profile

pytestmark = pytest.mark.integration
OCT = date(2026, 10, 1)


@pytest.fixture
def hr_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FileStorage:
    """The shared test HR key (see ``hr_support``)."""
    return configure_hr_storage(monkeypatch, tmp_path)


async def _point_everything_at(
    factory: Factory, team: AppraisalTeam, user: uuid.UUID
) -> uuid.UUID:
    """A row for every user column, each naming ``user``; returns the revision id."""
    async with factory() as db:
        goal = AppraisalGoal(
            org_id=team.org,
            profile_id=team.profile_id,
            cycle_id=team.cycle_id,
            target_period_start=OCT,
            origin=GoalOrigin.MANAGER_ADDED,
            status=GoalStatus.PROPOSED,
            proposed_by=user,
            accepted_by=user,
        )
        crypto.seal(goal, "title", "A goal")
        check_in = AppraisalCheckIn(
            id=uuid.uuid4(),
            org_id=team.org,
            profile_id=team.profile_id,
            cycle_id=team.cycle_id,
            period_start=OCT,
            period_end=date(2026, 10, 31),
            working_days=22,
            available_days=22,
        )
        link = AppraisalEvidenceLink(
            org_id=team.org,
            profile_id=team.profile_id,
            check_in_id=check_in.id,
            heading=EvidenceHeading.TEAM,
            added_by=user,
        )
        crypto.seal(link, "url", "https://example.com/doc")
        value = AppraisalGoalValue(
            org_id=team.org, goal_id=goal.id, check_in_id=check_in.id, reported_by=user
        )
        crypto.seal(value, "value", "7 of 9")
        revision = AppraisalGoalRevision(
            id=uuid.uuid4(),
            org_id=team.org,
            goal_id=goal.id,
            changed_by=user,
            kind=GoalRevisionKind.CREATED,
        )
        feedback = AppraisalManagerFeedback(
            org_id=team.org,
            cycle_id=team.cycle_id,
            profile_id=team.profile_id,
            manager_user_id=user,
            period_start=OCT,
            period_end=date(2026, 10, 31),
            cadence=CheckInCadence.MONTHLY,
            due_on=date(2026, 11, 14),
        )
        template = AppraisalRoleTemplate(
            org_id=team.org, name="Support", trends_approved_by=user, updated_by=user
        )
        db.add(goal)
        db.add(check_in)
        await db.flush()
        db.add_all([link, value, revision, feedback, template])
        for model, column in ((Appraisal, "manager_user_id"), (AppraisalCycle, "created_by")):
            await db.execute(update(model).where(model.org_id == team.org).values({column: user}))
        await db.commit()
        return revision.id


async def _count(factory: Factory, org: uuid.UUID, user: uuid.UUID) -> int:
    total = 0
    async with factory() as db:
        for column in USER_COLUMNS:
            model = column.class_
            stmt = (
                select(func.count()).select_from(model).where(model.org_id == org, column == user)
            )
            total += int((await db.execute(stmt)).scalar_one())
    return total


async def test_merge_repoints_every_user_column_and_keeps_history(
    pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    team = await appraisal_team(pg_session_factory)
    stub = await add_member_without_profile(pg_session_factory, team.org, "Ravi (GitHub)")
    revision_id = await _point_everything_at(pg_session_factory, team, stub)
    assert await _count(pg_session_factory, team.org, stub) == len(USER_COLUMNS)
    async with pg_session_factory() as db:
        result = await transfer_employee_record(
            db, org_id=team.org, source=stub, target=team.other
        )
        await db.commit()
    assert result.appraisal_rows_moved == len(USER_COLUMNS)
    assert await _count(pg_session_factory, team.org, stub) == 0
    assert await _count(pg_session_factory, team.org, team.other) == len(USER_COLUMNS)
    async with pg_session_factory() as db:
        revision = await db.get(AppraisalGoalRevision, revision_id)
        # History keeps who acted at the time, like the audit log.
        assert revision is not None and revision.changed_by == stub


async def test_merge_leaves_other_orgs_alone(
    pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    team = await appraisal_team(pg_session_factory)
    elsewhere = await appraisal_team(pg_session_factory)
    stub = await add_member_without_profile(pg_session_factory, team.org, "Ravi (GitHub)")
    await _point_everything_at(pg_session_factory, elsewhere, stub)
    async with pg_session_factory() as db:
        await transfer_employee_record(db, org_id=team.org, source=stub, target=team.other)
        await db.commit()
    assert await _count(pg_session_factory, elsewhere.org, stub) == len(USER_COLUMNS)


async def test_merge_refuses_to_make_someone_their_own_appraisal_manager(
    pg_session_factory: Factory,
) -> None:
    team = await appraisal_team(pg_session_factory)
    stub = await add_member_without_profile(pg_session_factory, team.org, "Ravi (GitHub)")
    async with pg_session_factory() as db:
        await db.execute(
            update(Appraisal).where(Appraisal.id == team.appraisal_id).values(manager_user_id=stub)
        )
        await db.commit()
    async with pg_session_factory() as db:
        with pytest.raises(EmployeeMergeConflictError, match="own appraisal manager"):
            await transfer_employee_record(db, org_id=team.org, source=stub, target=team.employee)
