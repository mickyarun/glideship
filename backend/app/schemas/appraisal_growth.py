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

"""The growth conversation over the API: a strength, a focus, next period's goals."""

import uuid
from datetime import date

from pydantic import BaseModel, Field

from app.models.appraisal_enums import GoalOrigin, GoalStatus


class GrowthBody(BaseModel):
    """One strength to use more and one thing to work on."""

    strength: str = Field("", max_length=500)
    focus: str = Field("", max_length=500)


class NextGoal(BaseModel):
    """A goal agreed for the next period."""

    id: uuid.UUID
    title: str
    measure: str
    status: GoalStatus
    origin: GoalOrigin
    proposed_by_name: str
    can_accept: bool
    can_remove: bool


class GrowthRead(BaseModel):
    """The conversation as the caller may see it; no band here."""

    open: bool
    can_edit: bool
    # Whether the viewer is the person: their adds are proposals, a manager's take a slot.
    is_self: bool
    strength: str
    focus: str
    next_period_start: date
    limit: int
    goals: list[NextGoal]
