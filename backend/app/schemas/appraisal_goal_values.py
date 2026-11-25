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

"""Each goal's value across the period's check-ins, as the API returns it."""

import uuid
from datetime import date

from pydantic import BaseModel


class GoalMonthValue(BaseModel):
    """One check-in's value for one goal."""

    check_in_id: uuid.UUID
    period_start: date
    value: str
    source_note: str | None = None
    source_url: str | None = None


class GoalValues(BaseModel):
    """One of the period's goals, with its value on each check-in the caller may read."""

    goal_id: uuid.UUID
    position: int
    title: str
    measure: str | None
    values: list[GoalMonthValue]
