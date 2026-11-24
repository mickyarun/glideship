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

"""The caller's appraisal to-do list as the API returns it."""

import uuid
from datetime import date
from enum import StrEnum

from pydantic import BaseModel


class TodoKind(StrEnum):
    """What the work is."""

    CHECK_IN = "check_in"
    SELF_REVIEW = "self_review"
    READ_RESULT = "read_result"
    NOTE = "note"
    MANAGER_REVIEW = "manager_review"
    CONFIRM_GOALS = "confirm_goals"
    SET_GOALS = "set_goals"
    OPEN_REVIEWS = "open_reviews"
    FAIRNESS_CHECK = "fairness_check"


class TodoRole(StrEnum):
    """Whose list it sits on: the caller's own, their team's, or the cycles HR runs."""

    OWN = "own"
    TEAM = "team"
    CYCLES = "cycles"


class TodoTarget(StrEnum):
    """What the item opens."""

    CHECK_IN = "check_in"
    REVIEW = "review"
    FEEDBACK = "feedback"
    GOALS = "goals"
    CYCLE = "cycle"


class TodoItem(BaseModel):
    """One thing the caller has to do."""

    kind: TodoKind
    role: TodoRole
    # Whose it is, for team work; empty for the caller's own and for cycles.
    person_name: str | None = None
    # The cycle's name, for HR's items.
    cycle_name: str | None = None
    due_on: date | None = None
    late: bool = False
    target: TodoTarget
    target_id: uuid.UUID
    # How many: goals to confirm or still to set, reviews in the fairness check.
    count: int | None = None
