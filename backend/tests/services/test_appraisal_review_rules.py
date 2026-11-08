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

"""Scoring rules, calibration figures and who may do what with a goal."""

import uuid

import pytest

from app.models.appraisal_enums import GoalOrigin, GoalResult, GoalStatus
from app.models.appraisal_goal import AppraisalGoal
from app.services.appraisals.calibration_math import Scored, figures
from app.services.appraisals.goal_rules import GoalRights, actions, next_position
from app.services.appraisals.review_rules import (
    BandDecision,
    GoalDecision,
    band_problem,
    final_band,
    final_result,
    goal_problem,
    self_problem,
)

ACHIEVED, PARTLY = GoalResult.ACHIEVED, GoalResult.PARTLY


def test_self_score_needs_a_band_evidence_for_high_bands_and_every_goal() -> None:
    assert self_problem(None, 0, {}) == "Pick an overall band."
    assert self_problem(2, 1, {}) == "Bands 1 and 2 need at least two pieces of evidence."
    assert self_problem(2, 2, {"g": None}) == "Score each goal: achieved, partly or not yet."
    assert self_problem(3, 0, {"g": ACHIEVED}) is None


@pytest.mark.parametrize(
    ("self_band", "decision", "problem"),
    [
        (3, BandDecision(True, None, "", 0), None),
        (None, BandDecision(True, None, "", 0), "There is no self-score to agree with."),
        (3, BandDecision(False, None, "x", 0), "Pick the band."),
        (3, BandDecision(False, 4, " ", 0), "Say why; they'll read this."),
        (
            3,
            BandDecision(False, 2, "Shipped", 1),
            "Band 1 or 2 needs at least two pieces of evidence.",
        ),
        (3, BandDecision(False, 5, "Missed", 0), "Band 5 needs evidence."),
        (3, BandDecision(False, 5, "Missed", 1), None),
        (None, BandDecision(False, 3, "From scratch", 0), None),
    ],
)
def test_manager_band_rules(
    self_band: int | None, decision: BandDecision, problem: str | None
) -> None:
    assert band_problem(self_band, decision) == problem


def test_the_final_value_is_the_employees_when_agreed_and_the_managers_when_changed() -> None:
    assert final_band(2, BandDecision(True, 4, "", 0)) == 2
    assert final_band(2, BandDecision(False, 3, "Reason", 0)) == 3
    assert final_result(ACHIEVED, GoalDecision(True, PARTLY, "")) is ACHIEVED
    assert final_result(ACHIEVED, GoalDecision(False, PARTLY, "Half shipped")) is PARTLY
    assert goal_problem(ACHIEVED, GoalDecision(False, PARTLY, "")) is not None
    assert goal_problem(None, GoalDecision(True, None, "")) is not None


def test_calibration_figures() -> None:
    team = [Scored(2, 2), Scored(3, 3), Scored(1, 3), Scored(None, 4)]
    figs = figures(team)
    assert figs.bands == {1: 0, 2: 1, 3: 2, 4: 1, 5: 0}
    assert figs.agreement == pytest.approx(2 / 3)
    assert figs.gaps == 1 and figs.flag is None
    assert figures([Scored(3, 3)] * 3).flag == "Agreed with every self-score."
    assert figures([Scored(1, 3)] * 5).flag == "Changed nearly every self-score."
    assert figures([Scored(3, 3)] * 2).flag is None
    assert figures([Scored(None, 3)]).agreement is None


def _goal(status: GoalStatus, origin: GoalOrigin) -> AppraisalGoal:
    return AppraisalGoal(id=uuid.uuid4(), status=status, origin=origin, suggestion_refs={})


def test_goal_actions_by_role() -> None:
    employee, manager = GoalRights(True, False), GoalRights(False, True)
    proposed = _goal(GoalStatus.PROPOSED, GoalOrigin.EMPLOYEE_OWN)
    assert (
        actions(proposed, manager, False).accept and actions(proposed, manager, False).ask_reword
    )
    assert not actions(proposed, employee, False).accept
    assert actions(proposed, employee, False).edit and actions(proposed, employee, False).dismiss
    confirmed = _goal(GoalStatus.ACCEPTED, GoalOrigin.EMPLOYEE_OWN)
    assert actions(confirmed, employee, False).suggest_change
    assert not actions(confirmed, employee, True).suggest_change
    assert not actions(confirmed, employee, False).edit
    assert not actions(confirmed, manager, False).remove
    assert actions(_goal(GoalStatus.ACCEPTED, GoalOrigin.MANAGER_ADDED), manager, False).remove
    suggested = _goal(GoalStatus.SUGGESTED, GoalOrigin.AI_SUGGESTED)
    assert actions(suggested, employee, False).accept and actions(suggested, manager, False).accept
    locked = GoalRights(False, False)
    assert actions(proposed, locked, False) == actions(confirmed, locked, False)


def test_next_position() -> None:
    assert next_position(set()) == 1
    assert next_position({1, 3}) == 2
    assert next_position({1, 2, 3}) is None
