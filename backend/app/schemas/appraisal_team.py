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

"""A manager's team at a glance: each report's goals, check-ins and notes."""

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.schemas.appraisal_goal import AppraisalSummary

# sent; late (past due, not sent); open (not sent, not due yet); missed
# (closed unsent); not_open (the month hasn't opened yet).
MonthStateName = Literal["sent", "late", "open", "missed", "not_open"]


class MonthState(BaseModel):
    """One check-in period of the cycle, as the manager may see it."""

    period_start: date
    period_end: date
    check_in_id: uuid.UUID | None
    state: MonthStateName
    due_on: date | None


class NoteState(BaseModel):
    """One of the manager's notes for this person: whether it is sent, and when due."""

    id: uuid.UUID
    period_start: date
    period_end: date
    sent: bool
    due_on: date | None
    late: bool


class TeamRow(AppraisalSummary):
    """A report's appraisal, with their check-ins month by month and the manager's notes."""

    months: list[MonthState]
    notes: list[NoteState]
    # The org's goal range per person, for the first-visit plan.
    min_goals: int
    max_goals: int
    # The cycle's working days for a note after its check-in is sent, and its goals date.
    note_due_days: int
    goals_due: date
