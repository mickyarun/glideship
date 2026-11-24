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

"""Who's done and who's late in a running cycle, for HR: counts and states, no content."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.models.appraisal_enums import AppraisalStatus
from app.schemas.appraisal_team import MonthStateName


class ProgressRow(BaseModel):
    """One enrolled person's progress through the cycle."""

    user_id: uuid.UUID
    name: str
    manager_user_id: uuid.UUID | None
    manager_name: str
    status: AppraisalStatus
    goals_accepted: int
    # Each check-in period's state, in order, as anyone but the person sees it.
    months: list[MonthStateName]
    check_ins: int
    check_ins_added: int
    check_ins_missed: int
    check_ins_late: int
    feedback: int
    feedback_done: int
    feedback_overdue: int


class ManagerOverdue(BaseModel):
    """A manager with notes still unsent past their due date."""

    name: str
    overdue: int


class PeriodCount(BaseModel):
    """How much of one period's work is sent: check-ins, or managers' notes."""

    period_start: date
    period_end: date
    # The earliest due date given in the period, if any opened yet.
    due_on: date | None
    sent: int
    total: int


class CycleProgress(BaseModel):
    """Who's done and who's late, with each month's counts and the goal floor."""

    people: list[ProgressRow]
    feedback: int
    feedback_done: int
    managers_overdue: list[ManagerOverdue]
    min_goals: int
    check_in_periods: list[PeriodCount]
    note_periods: list[PeriodCount]
    # People a manual reminder would reach now: late check-ins and late notes.
    remind_count: int
    reminded_at: datetime | None


class RemindResult(BaseModel):
    """What HR's manual reminder did."""

    people: int
    reached: int
