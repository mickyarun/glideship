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

"""Every appraisal table constraint refuses the row it exists to refuse.

Each case builds one bad row and expects that exact constraint by name,
so a test can't pass because some other rule happened to fire.
"""

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.appraisal import Appraisal
from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_enums import (
    CheckInCadence,
    DraftingMode,
    FeedbackCadence,
    FeedbackStatus,
    GoalOrigin,
    GoalStatus,
    ReviewPeriod,
)
from app.models.appraisal_goal import AppraisalGoal
from app.models.appraisal_goal_value import AppraisalGoalValue
from app.models.appraisal_manager_feedback import AppraisalManagerFeedback
from app.models.appraisal_role_template import AppraisalRoleTemplate
from app.repositories.base import violated_constraint
from app.services.appraisals import crypto
from app.services.file_storage import FileStorage
from tests.integration.appraisal_support import (
    AppraisalTeam,
    add_and_commit,
    appraisal_team,
    cycle_row,
)
from tests.integration.hr_support import configure_hr_storage
from tests.integration.leave_support import Factory

pytestmark = pytest.mark.integration
OCT = date(2026, 10, 1)

Rows = Callable[[AppraisalTeam], list[Any]]


@pytest.fixture
def hr_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FileStorage:
    """The shared test HR key (see ``hr_support``)."""
    return configure_hr_storage(monkeypatch, tmp_path)


def _check_in(team: AppraisalTeam, **kw: Any) -> AppraisalCheckIn:
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "org_id": team.org,
        "profile_id": team.profile_id,
        "cycle_id": team.cycle_id,
        "period_start": OCT,
        "period_end": date(2026, 10, 31),
        "working_days": 22,
        "available_days": 20,
    }
    return AppraisalCheckIn(**(values | kw))


def _goal(team: AppraisalTeam, **kw: Any) -> AppraisalGoal:
    values: dict[str, Any] = {
        "org_id": team.org,
        "profile_id": team.profile_id,
        "cycle_id": team.cycle_id,
        "target_period_start": OCT,
        "origin": GoalOrigin.EMPLOYEE_OWN,
        "status": GoalStatus.PROPOSED,
    }
    goal = AppraisalGoal(**(values | kw))
    crypto.seal(goal, "title", "A goal")
    return goal


def _feedback(team: AppraisalTeam, **kw: Any) -> AppraisalManagerFeedback:
    values: dict[str, Any] = {
        "org_id": team.org,
        "cycle_id": team.cycle_id,
        "profile_id": team.profile_id,
        "manager_user_id": team.manager,
        "period_start": OCT,
        "period_end": date(2026, 10, 31),
        "cadence": CheckInCadence.MONTHLY,
        "due_on": date(2026, 11, 14),
    }
    return AppraisalManagerFeedback(**(values | kw))


def _template(team: AppraisalTeam, name: str, *, default: bool = False) -> AppraisalRoleTemplate:
    return AppraisalRoleTemplate(org_id=team.org, name=name, is_default=default)


def _goal_value(team: AppraisalTeam) -> list[Any]:
    check_in, goal = _check_in(team), _goal(team)
    values = []
    for _ in range(2):
        value = AppraisalGoalValue(org_id=team.org, goal_id=goal.id, check_in_id=check_in.id)
        crypto.seal(value, "value", "6 days")
        values.append(value)
    return [check_in, goal, *values]


def _cadence(review: ReviewPeriod, checkins: CheckInCadence, feedback: FeedbackCadence) -> Rows:
    return lambda t: [
        cycle_row(t.org, review_period=review, checkin_cadence=checkins, feedback_cadence=feedback)
    ]


CASES: list[tuple[str, Rows]] = [
    (
        "ck_appraisal_cycles_period",
        lambda t: [cycle_row(t.org, period_end=OCT, enrolment_cutoff=OCT)],
    ),
    ("ck_appraisal_cycles_due_dates", lambda t: [cycle_row(t.org, ack_due=date(2027, 1, 13))]),
    (
        "ck_appraisal_cycles_cutoff",
        lambda t: [cycle_row(t.org, enrolment_cutoff=date(2027, 2, 1))],
    ),
    ("ck_appraisal_cycles_offsets", lambda t: [cycle_row(t.org, hr_overdue_offset=-1)]),
    (
        "ck_appraisal_cycles_feedback_cadence",
        _cadence(ReviewPeriod.HALF_YEARLY, CheckInCadence.MONTHLY, FeedbackCadence.IN_REVIEW),
    ),
    (
        "ck_appraisal_cycles_feedback_cadence",
        _cadence(ReviewPeriod.QUARTERLY, CheckInCadence.MONTHLY, FeedbackCadence.QUARTERLY),
    ),
    (
        "ck_appraisal_cycles_feedback_cadence",
        _cadence(ReviewPeriod.YEARLY, CheckInCadence.QUARTERLY, FeedbackCadence.MONTHLY),
    ),
    (
        "ck_appraisal_cycles_checkin_cadence",
        _cadence(ReviewPeriod.QUARTERLY, CheckInCadence.QUARTERLY, FeedbackCadence.IN_REVIEW),
    ),
    ("ck_appraisal_check_ins_period", lambda t: [_check_in(t, period_end=OCT)]),
    ("ck_appraisal_check_ins_days", lambda t: [_check_in(t, available_days=23)]),
    ("uq_appraisal_check_ins_period", lambda t: [_check_in(t), _check_in(t)]),
    ("ck_appraisal_goals_position", lambda t: [_goal(t, position=4)]),
    (
        "ck_appraisal_goals_suggestion_basis",
        lambda t: [_goal(t, origin=GoalOrigin.AI_SUGGESTED, status=GoalStatus.SUGGESTED)],
    ),
    ("ck_appraisal_goals_accepted_position", lambda t: [_goal(t, status=GoalStatus.ACCEPTED)]),
    (
        "uq_appraisal_goals_accepted_position",
        lambda t: [_goal(t, status=GoalStatus.ACCEPTED, position=1) for _ in range(2)],
    ),
    ("ck_appraisal_feedback_period", lambda t: [_feedback(t, period_end=OCT)]),
    ("ck_appraisal_feedback_done_at", lambda t: [_feedback(t, status=FeedbackStatus.DONE)]),
    ("uq_appraisal_feedback_period", lambda t: [_feedback(t), _feedback(t)]),
    ("uq_appraisal_goal_values_check_in", _goal_value),
    (
        "uq_appraisal_role_templates_name",
        lambda t: [_template(t, "Support"), _template(t, "Support")],
    ),
    (
        "uq_appraisal_role_templates_default",
        lambda t: [_template(t, "General", default=True), _template(t, "Other", default=True)],
    ),
]


@pytest.mark.parametrize(
    ("constraint", "rows"), CASES, ids=[f"{i}-{c[0]}" for i, c in enumerate(CASES)]
)
async def test_constraint_refuses_its_bad_row(
    pg_session_factory: Factory, hr_key: FileStorage, constraint: str, rows: Rows
) -> None:
    team = await appraisal_team(pg_session_factory)
    async with pg_session_factory() as db:
        *good, bad = rows(team)
        for row in good:
            db.add(row)
            await db.flush()
        db.add(bad)
        with pytest.raises(IntegrityError) as raised:
            await db.flush()
    assert violated_constraint(raised.value) == constraint


@pytest.mark.parametrize(
    ("field", "value", "constraint"),
    [
        ("self_band", 6, "ck_appraisals_self_band"),
        ("manager_band", 0, "ck_appraisals_manager_band"),
        ("final_band", 9, "ck_appraisals_final_band"),
        (
            "self_submitted_at",
            datetime(2027, 1, 5, tzinfo=UTC),
            "ck_appraisals_self_submitted_band",
        ),
        (
            "manager_submitted_at",
            datetime(2027, 1, 9, tzinfo=UTC),
            "ck_appraisals_manager_submitted_band",
        ),
    ],
)
async def test_appraisal_band_rules(
    pg_session_factory: Factory, field: str, value: Any, constraint: str
) -> None:
    team = await appraisal_team(pg_session_factory)
    async with pg_session_factory() as db:
        appraisal = await db.get(Appraisal, team.appraisal_id)
        assert appraisal is not None
        setattr(appraisal, field, value)
        with pytest.raises(IntegrityError) as raised:
            await db.flush()
    assert violated_constraint(raised.value) == constraint


async def test_one_appraisal_per_person_per_cycle(pg_session_factory: Factory) -> None:
    team = await appraisal_team(pg_session_factory)
    duplicate = Appraisal(
        org_id=team.org,
        cycle_id=team.cycle_id,
        profile_id=team.profile_id,
        manager_user_id=team.manager,
        drafting_mode=DraftingMode.MANUAL,
    )
    async with pg_session_factory() as db:
        with pytest.raises(IntegrityError, match="uq_appraisals_cycle_profile"):
            await add_and_commit(db, duplicate)


@pytest.mark.parametrize(
    ("review", "checkins", "feedback"),
    [
        (ReviewPeriod.QUARTERLY, CheckInCadence.MONTHLY, FeedbackCadence.MONTHLY),
        (ReviewPeriod.QUARTERLY, CheckInCadence.MONTHLY, FeedbackCadence.IN_REVIEW),
        (ReviewPeriod.HALF_YEARLY, CheckInCadence.MONTHLY, FeedbackCadence.QUARTERLY),
        (ReviewPeriod.HALF_YEARLY, CheckInCadence.QUARTERLY, FeedbackCadence.QUARTERLY),
        (ReviewPeriod.YEARLY, CheckInCadence.QUARTERLY, FeedbackCadence.QUARTERLY),
    ],
)
async def test_cycle_accepts_cadences_that_fit(
    pg_session_factory: Factory,
    review: ReviewPeriod,
    checkins: CheckInCadence,
    feedback: FeedbackCadence,
) -> None:
    team = await appraisal_team(pg_session_factory)
    async with pg_session_factory() as db:
        await add_and_commit(db, _cadence(review, checkins, feedback)(team)[0])


async def test_dismissed_goals_may_share_a_position(
    pg_session_factory: Factory, hr_key: FileStorage
) -> None:
    team = await appraisal_team(pg_session_factory)
    async with pg_session_factory() as db:
        db.add(_goal(team, status=GoalStatus.ACCEPTED, position=1))
        db.add(_goal(team, status=GoalStatus.DISMISSED, position=1))
        await db.commit()


async def test_one_default_template_is_allowed(pg_session_factory: Factory) -> None:
    team = await appraisal_team(pg_session_factory)
    async with pg_session_factory() as db:
        db.add(_template(team, "General", default=True))
        db.add(_template(team, "Support"))
        await db.commit()
