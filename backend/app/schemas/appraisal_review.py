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

"""The end-of-period review over the API: evidence, self-score, manager review, result."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.appraisal_enums import (
    AppraisalStatus,
    CheckInStatus,
    DraftingMode,
    DraftStatus,
    GoalResult,
)
from app.schemas.appraisal_check_in import AiLine, CheckInNote, FactView, LinkRead

Band = int


class TimelineMonth(BaseModel):
    """One check-in in the period: the facts, the person's words and links."""

    check_in_id: uuid.UUID
    period_start: date
    status: CheckInStatus
    facts: list[FactView]
    note: CheckInNote
    links: list[LinkRead]


class ReviewGoal(BaseModel):
    """A confirmed goal with its scores, as far as the caller may see them."""

    id: uuid.UUID
    position: int | None
    title: str
    measure: str
    added_mid_period: bool
    accepted_at: datetime | None
    self_result: GoalResult | None
    self_reason: str | None
    self_evidence: list[str]
    # The manager's result: shown to the employee once the result is shared.
    result: GoalResult | None
    manager_reason: str | None


class SelfScore(BaseModel):
    """The employee's overall band."""

    band: Band | None
    reason: str
    evidence: list[str]
    submitted_at: datetime | None


class ManagerScore(BaseModel):
    """The manager's overall band, and the final one once submitted."""

    band: Band | None
    reason: str
    evidence: list[str]
    final_band: Band | None
    submitted_at: datetime | None


class ManagerOnly(BaseModel):
    """Answers only the manager (and HR, once submitted) see; never the employee."""

    ready_next_level: bool | None
    performance_concern: bool | None
    concern_note: str


class ReviewActions(BaseModel):
    """What the caller may do now."""

    edit_self: bool
    edit_manager: bool
    send_back: bool
    share: bool
    acknowledge: bool


class AppraisalRead(BaseModel):
    """One appraisal as the caller may see it."""

    id: uuid.UUID
    user_id: uuid.UUID
    person_name: str
    manager_name: str | None
    cycle_name: str
    period_start: date
    period_end: date
    self_due: date
    manager_due: date
    ack_due: date
    status: AppraisalStatus
    drafting_mode: DraftingMode
    summary_status: DraftStatus
    summary: list[AiLine]
    summary_hidden: bool
    timeline: list[TimelineMonth]
    period_facts: list[FactView]
    goals: list[ReviewGoal]
    self_score: SelfScore | None
    manager_score: ManagerScore | None
    manager_only: ManagerOnly | None
    send_back_note: str | None
    reply: str | None
    shared_at: datetime | None
    acknowledged_at: datetime | None
    can: ReviewActions


class SelfGoalIn(BaseModel):
    """The employee's result for one goal."""

    goal_id: uuid.UUID
    result: GoalResult | None = None
    reason: str = Field("", max_length=300)
    evidence: list[str] = Field(default_factory=list, max_length=5)


class SelfBody(BaseModel):
    """The self-review as saved so far."""

    band: Band | None = Field(None, ge=1, le=5)
    reason: str = Field("", max_length=600)
    evidence: list[str] = Field(default_factory=list, max_length=10)
    goals: list[SelfGoalIn] = Field(default_factory=list, max_length=3)


class ManagerGoalIn(BaseModel):
    """The manager's call on one goal: agree, or a result and a reason."""

    goal_id: uuid.UUID
    agree: bool = False
    result: GoalResult | None = None
    reason: str = Field("", max_length=300)


class ManagerBody(BaseModel):
    """The manager's review as saved so far."""

    agree: bool = False
    band: Band | None = Field(None, ge=1, le=5)
    reason: str = Field("", max_length=600)
    evidence: list[str] = Field(default_factory=list, max_length=10)
    goals: list[ManagerGoalIn] = Field(default_factory=list, max_length=3)
    ready_next_level: bool | None = None
    performance_concern: bool | None = None
    concern_note: str = Field("", max_length=500)


class NoteBody(BaseModel):
    """HR's note when sending a review back; the manager reads it."""

    note: str = Field(min_length=1, max_length=600)


class ReplyBody(BaseModel):
    """The employee's optional reply when acknowledging; HR reads it too."""

    reply: str = Field("", max_length=1000)


class CalibrationPerson(BaseModel):
    """One reviewed person in calibration: bands and states, no reasons."""

    appraisal_id: uuid.UUID
    name: str
    manager_name: str
    status: AppraisalStatus
    self_band: Band | None
    final_band: Band | None
    gap: bool
    feedback: int
    feedback_done: int


class CalibrationTeam(BaseModel):
    """One manager's figures."""

    manager_name: str
    people: int
    bands: dict[int, int]
    agreement: float | None
    gaps: int
    flag: str | None


class Calibration(BaseModel):
    """The cycle's calibration view."""

    teams: list[CalibrationTeam]
    people: list[CalibrationPerson]
