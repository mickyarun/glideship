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

"""Manager feedback over the API."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.appraisal_enums import CheckInCadence, CheckInStatus, FeedbackStatus, GoalCheck


class GoalCheckIn(BaseModel):
    """The manager's status for one goal, with an optional note."""

    goal_id: uuid.UUID
    status: GoalCheck
    note: str = Field("", max_length=300)


class FeedbackBody(BaseModel):
    """What the manager writes: one line to keep doing, one to try next."""

    keep: str = Field("", max_length=500)
    try_next: str = Field("", max_length=500)
    # The full set of statuses; left out (null), the saved ones are kept.
    goals: list[GoalCheckIn] | None = Field(None, max_length=10)


class FeedbackGoal(BaseModel):
    """A goal as the feedback page shows it."""

    id: uuid.UUID
    title: str
    status: GoalCheck | None = None
    note: str = ""


class FeedbackCheckIn(BaseModel):
    """One check-in the feedback covers, for the manager to read first."""

    id: uuid.UUID
    period_start: date
    status: CheckInStatus
    closed: bool


class FeedbackRow(BaseModel):
    """A line in the manager's team list."""

    id: uuid.UUID
    profile_id: uuid.UUID
    person_name: str
    period_start: date
    period_end: date
    cadence: CheckInCadence
    due_on: date
    status: FeedbackStatus
    overdue: bool
    check_ins: int
    check_ins_added: int


class FeedbackRead(BaseModel):
    """One feedback item for one viewer."""

    id: uuid.UUID
    profile_id: uuid.UUID
    person_name: str
    manager_name: str | None
    period_start: date
    period_end: date
    cadence: CheckInCadence
    due_on: date
    status: FeedbackStatus
    done_at: datetime | None
    overdue: bool
    can_edit: bool
    keep: str
    try_next: str
    goals: list[FeedbackGoal]
    check_ins: list[FeedbackCheckIn]


class FeedbackShown(BaseModel):
    """The manager's feedback as it appears on the employee's check-in."""

    manager_name: str | None
    period_start: date
    period_end: date
    cadence: CheckInCadence
    done: bool
    keep: str
    try_next: str
    goals: list[FeedbackGoal]
