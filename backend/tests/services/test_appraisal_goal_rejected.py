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

"""A goal counts as rejected only when it is the person's own and the manager rejected it."""

import uuid

from app.models.appraisal_enums import GoalRevisionKind, GoalStatus
from app.models.appraisal_goal import AppraisalGoal
from app.services.appraisals.goal_rules import is_rejected

PERSON = uuid.uuid4()
CREATED, DECLINED, REMOVED = (
    GoalRevisionKind.CREATED,
    GoalRevisionKind.DECLINED,
    GoalRevisionKind.REMOVED,
)


def _goal(status: GoalStatus = GoalStatus.DISMISSED, by: uuid.UUID = PERSON) -> AppraisalGoal:
    return AppraisalGoal(status=status, proposed_by=by, suggestion_refs={})


def test_the_managers_rejection_of_the_persons_goal() -> None:
    assert is_rejected(_goal(), PERSON, [CREATED, DECLINED])


def test_withdrawn_by_the_person_is_not_rejected() -> None:
    assert not is_rejected(_goal(), PERSON, [CREATED, REMOVED])


def test_a_goal_someone_else_proposed_is_not_rejected() -> None:
    assert not is_rejected(_goal(by=uuid.uuid4()), PERSON, [CREATED, DECLINED])


def test_a_live_goal_is_not_rejected() -> None:
    assert not is_rejected(_goal(GoalStatus.PROPOSED), PERSON, [CREATED, DECLINED])
    assert not is_rejected(_goal(), PERSON, [])
