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

"""Appraisal cycles over the API."""

import uuid
from datetime import date
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.appraisal_enums import CheckInCadence, CycleStatus, FeedbackCadence, ReviewPeriod


class CycleScope(BaseModel):
    """Who a cycle covers; empty lists mean everyone active."""

    offices: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    departments: list[str] = Field(default_factory=list, max_length=50)
    templates: list[uuid.UUID] = Field(default_factory=list, max_length=50)


class CycleCreate(BaseModel):
    """A new cycle. Anything left out is copied from the org's settings."""

    name: str | None = Field(None, min_length=1, max_length=120)
    period_start: date | None = None
    review_period: ReviewPeriod | None = None
    checkin_cadence: CheckInCadence | None = None
    feedback_cadence: FeedbackCadence | None = None
    ai_drafting: bool | None = None
    suggest_goals_on_open: bool | None = None
    scope: CycleScope = Field(default_factory=CycleScope)
    template_overrides: dict[str, uuid.UUID] = Field(default_factory=dict, max_length=100)
    intro_note: str | None = Field(None, max_length=2000)

    @model_validator(mode="after")
    def _first_of_month(self) -> Self:
        if self.period_start is not None and self.period_start.day != 1:
            raise ValueError("A cycle starts on the first of a month.")
        return self


class CycleUpdate(BaseModel):
    """Changes to a draft cycle."""

    name: str | None = Field(None, min_length=1, max_length=120)
    self_due: date | None = None
    manager_due: date | None = None
    ack_due: date | None = None
    feedback_due_days: int | None = Field(None, ge=0, le=60)
    reminder_offsets: list[int] | None = Field(None, max_length=6)
    ai_drafting: bool | None = None
    scope: CycleScope | None = None
    template_overrides: dict[str, uuid.UUID] | None = Field(None, max_length=100)
    intro_note: str | None = Field(None, max_length=2000)


class CycleRead(BaseModel):
    """A cycle as the API returns it."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    status: CycleStatus
    period_start: date
    period_end: date
    self_due: date
    manager_due: date
    ack_due: date
    review_period: ReviewPeriod
    checkin_cadence: CheckInCadence
    feedback_cadence: FeedbackCadence
    feedback_due_days: int
    reminder_offsets: list[int]
    ai_drafting: bool
    suggest_goals_on_open: bool
    enrolment_cutoff: date
    scope: CycleScope
    template_overrides: dict[str, uuid.UUID]


class EnrolmentReport(BaseModel):
    """What happened when a cycle opened, for HR to follow up."""

    enrolled: int
    already_enrolled: int
    no_primary_manager: list[uuid.UUID]
    no_template: list[uuid.UUID]
