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

"""The org's appraisal settings: defaults every new cycle copies."""

from typing import Any, Self

from pydantic import BaseModel, Field, model_validator

from app.models.appraisal_enums import CheckInCadence, FeedbackCadence, ReviewPeriod
from app.services.appraisals.cadence import cadence_error

# The most confirmed goals an org may allow per person per period.
MAX_GOALS_CAP = 20
# The usual floor: settings saved before there was one get this, or their
# max_goals when that is lower.
DEFAULT_MIN_GOALS = 3


class AppraisalSettings(BaseModel):
    """Stored under ``organizations.config["appraisals"]``."""

    review_period: ReviewPeriod = ReviewPeriod.QUARTERLY
    checkin_cadence: CheckInCadence = CheckInCadence.MONTHLY
    feedback_cadence: FeedbackCadence = FeedbackCadence.MONTHLY
    # Off means everyone gets the manual check-in, whatever the provider.
    ai_enabled: bool = True
    # Working days after a check-in period ends that the check-in is due.
    checkin_due_days: int = Field(5, ge=1, le=20)
    # Working days after a check-in is sent that the manager's note is due.
    feedback_due_days: int = Field(5, ge=1, le=20)
    self_due_days: int = Field(7, ge=0, le=60)
    manager_due_days: int = Field(14, ge=0, le=90)
    ack_due_days: int = Field(28, ge=0, le=120)
    # Working days relative to each due date.
    reminder_offsets: list[int] = Field(default_factory=lambda: [-3, 0, 2], max_length=6)
    overdue_nudge: bool = True
    hr_overdue_list: bool = True
    hr_overdue_offset: int = Field(3, ge=0, le=30)
    suggest_goals_on_open: bool = False
    # Confirmed goals per person per period. Read live, not copied onto a
    # cycle, so raising it applies to a running cycle; lowering it keeps
    # goals already confirmed and only stops new ones.
    max_goals: int = Field(3, ge=1, le=MAX_GOALS_CAP)
    # The fewest confirmed goals a person should have; below it, the
    # manager's to-do list asks for more. Never above max_goals.
    min_goals: int = Field(DEFAULT_MIN_GOALS, ge=1, le=MAX_GOALS_CAP)

    @model_validator(mode="before")
    @classmethod
    def _floor_for_old_settings(cls, data: Any) -> Any:
        """Settings saved before min_goals existed get the floor their max allows."""
        top = data.get("max_goals") if isinstance(data, dict) else None
        if isinstance(top, int) and "min_goals" not in data:
            return {**data, "min_goals": min(DEFAULT_MIN_GOALS, top)}
        return data

    @model_validator(mode="after")
    def _rules(self) -> Self:
        problem = cadence_error(self.review_period, self.checkin_cadence, self.feedback_cadence)
        if problem:
            raise ValueError(problem)
        if not self.self_due_days <= self.manager_due_days <= self.ack_due_days:
            raise ValueError("Due dates must run self-score, then manager review, then reply.")
        if self.min_goals > self.max_goals:
            raise ValueError("The fewest goals can't be more than the most goals.")
        if any(not -10 <= offset <= 10 for offset in self.reminder_offsets):
            raise ValueError("Reminder offsets must be within 10 working days of the due date.")
        return self
