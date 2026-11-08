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

"""Goals over the API: proposing, confirming, editing and their history."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.appraisal_enums import (
    AppraisalStatus,
    GoalOrigin,
    GoalResult,
    GoalRevisionKind,
    GoalStatus,
    SuggestionBasis,
)


class GoalBody(BaseModel):
    """A new goal: an outcome, how you'll know, and (from a manager) why now."""

    title: str = Field(min_length=1, max_length=200)
    measure: str = Field("", max_length=300)
    reason: str = Field("", max_length=300)
    # Picked from the role template's library rather than written from scratch.
    source: Literal["role_library"] | None = None


class GoalEdit(BaseModel):
    """New wording; a manager changing a confirmed goal must say why."""

    title: str = Field(min_length=1, max_length=200)
    measure: str = Field("", max_length=300)
    reason: str = Field("", max_length=300)


class ReasonBody(BaseModel):
    """A line the employee sees: why a goal was declined, or what to reword."""

    reason: str = Field("", max_length=300)


class GoalWords(BaseModel):
    """A goal's words at one point in its history."""

    title: str
    measure: str


class HistoryRead(BaseModel):
    """One line of a goal's history."""

    kind: GoalRevisionKind
    by_name: str
    at: datetime
    before: GoalWords | None
    after: GoalWords | None
    reason: str | None


class GoalActionsRead(BaseModel):
    """What the caller may do with this goal right now."""

    accept: bool
    dismiss: bool
    ask_reword: bool
    edit: bool
    remove: bool
    suggest_change: bool


class GoalRead(BaseModel):
    """One goal as the caller may see it."""

    id: uuid.UUID
    position: int | None
    title: str
    measure: str
    origin: GoalOrigin
    status: GoalStatus
    suggestion_basis: SuggestionBasis | None
    proposed_by_name: str
    added_mid_period: bool
    created_at: datetime
    # A proposed change to a confirmed goal names the goal it would replace.
    replaces: uuid.UUID | None
    dismiss_reason: str | None
    reword_note: str | None
    history: list[HistoryRead]
    actions: GoalActionsRead


class GoalsRead(BaseModel):
    """A person's goals for one review period."""

    appraisal_id: uuid.UUID
    person_name: str
    manager_name: str | None
    period_start: date
    period_end: date
    locked: bool
    limit: int
    accepted: int
    can_propose: bool
    can_add: bool
    goals: list[GoalRead]


class GoalOption(BaseModel):
    """A starting point for a goal, with no AI: the role library or last period."""

    source: Literal["role_library", "last_period"]
    title: str
    measure: str
    measure_source: str
    last_result: GoalResult | None = None


class AppraisalSummary(BaseModel):
    """A row in "my appraisals" or the team's: where each review has got to."""

    id: uuid.UUID
    user_id: uuid.UUID
    person_name: str
    cycle_name: str
    period_start: date
    period_end: date
    status: AppraisalStatus
    goals_accepted: int
    goals_proposed: int
