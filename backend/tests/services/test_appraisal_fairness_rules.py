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

"""Who rates high, who acts on a change the manager suggested, and when goals are due (pure)."""

import uuid
from datetime import date

from app.models.appraisal_enums import GoalOrigin, GoalStatus
from app.models.appraisal_goal import FROM_MANAGER, AppraisalGoal
from app.services.appraisals.calibration_math import (
    HighShare,
    Scored,
    high_share,
    rates_high,
    waiting_to_compare,
)
from app.services.appraisals.cycle_people import goals_due_for
from app.services.appraisals.goal_rules import GoalRights, actions


def test_a_manager_rates_high_only_against_others() -> None:
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    assert high_share([Scored(None, 1), Scored(3, 2), Scored(3, 3)]) == HighShare(2, 3)
    # Three of three Exceeded against one in three elsewhere.
    assert rates_high({a: HighShare(3, 3), b: HighShare(1, 3)}) == {a}
    # Nobody else to compare with: no pattern.
    assert rates_high({a: HighShare(3, 3)}) == set()
    assert rates_high({a: HighShare(3, 3), b: HighShare(0, 0)}) == set()
    # Everyone rates that way: nobody stands out.
    assert rates_high({a: HighShare(3, 3), b: HighShare(2, 3)}) == set()
    # Too few reviews to call it.
    assert rates_high({a: HighShare(2, 2), b: HighShare(0, 4)}) == set()
    # Others together, not one at a time: b alone is high, but b and c are not.
    assert rates_high({a: HighShare(3, 3), b: HighShare(2, 2), c: HighShare(0, 4)}) == {a}


def test_the_person_decides_on_a_change_their_manager_suggested() -> None:
    employee, manager = GoalRights(True, False), GoalRights(False, True)
    change = AppraisalGoal(
        id=uuid.uuid4(),
        status=GoalStatus.PROPOSED,
        origin=GoalOrigin.MANAGER_ADDED,
        suggestion_refs={"replaces": str(uuid.uuid4()), "from": FROM_MANAGER},
    )
    mine = actions(change, employee, False)
    assert mine.accept and mine.dismiss and not mine.edit and not mine.ask_reword
    theirs = actions(change, manager, False)
    assert not theirs.accept and theirs.dismiss and theirs.edit and not theirs.ask_reword
    confirmed = AppraisalGoal(
        id=uuid.uuid4(), status=GoalStatus.ACCEPTED, origin=GoalOrigin.EMPLOYEE_OWN
    )
    confirmed.suggestion_refs = {}
    assert actions(confirmed, manager, False).suggest_change
    assert not actions(confirmed, manager, True).suggest_change


def test_someone_enrolled_late_gets_the_same_window_for_goals() -> None:
    start, due = date(2026, 10, 1), date(2026, 10, 8)
    assert goals_due_for(due, start, date(2026, 10, 1)) == due
    assert goals_due_for(due, start, due) == due
    # Enrolled on 20 October: a week, as everyone had, from then.
    assert goals_due_for(due, start, date(2026, 10, 20)) == date(2026, 10, 27)


def test_a_high_rating_team_with_nobody_to_compare_waits() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    # Alone and rating high: not judged, but held until others arrive.
    assert waiting_to_compare({a: HighShare(3, 3)}) == {a}
    assert waiting_to_compare({a: HighShare(3, 3), b: HighShare(0, 0)}) == {a}
    # Alone but not rating high, or too small to call: nothing to wait for.
    assert waiting_to_compare({a: HighShare(1, 3)}) == set()
    assert waiting_to_compare({a: HighShare(2, 2)}) == set()
    # Once another team's reviews are in, the usual rule decides instead.
    assert waiting_to_compare({a: HighShare(3, 3), b: HighShare(0, 1)}) == set()
