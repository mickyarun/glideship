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

from typing import Self

from pydantic import BaseModel, Field, model_validator

from app.models.appraisal_enums import CheckInCadence, FeedbackCadence, ReviewPeriod
from app.services.appraisals.cadence import cadence_error


class AppraisalSettings(BaseModel):
    """Stored under ``organizations.config["appraisals"]``."""

    review_period: ReviewPeriod = ReviewPeriod.QUARTERLY
    checkin_cadence: CheckInCadence = CheckInCadence.MONTHLY
    feedback_cadence: FeedbackCadence = FeedbackCadence.MONTHLY
    # Off means everyone gets the manual check-in, whatever the provider.
    ai_enabled: bool = True
    feedback_due_days: int = Field(10, ge=0, le=60)
    self_due_days: int = Field(7, ge=0, le=60)
    manager_due_days: int = Field(14, ge=0, le=90)
    ack_due_days: int = Field(28, ge=0, le=120)
    # Working days relative to each due date.
    reminder_offsets: list[int] = Field(default_factory=lambda: [-3, 0, 2], max_length=6)
    overdue_nudge: bool = True
    hr_overdue_list: bool = True
    hr_overdue_offset: int = Field(3, ge=0, le=30)
    suggest_goals_on_open: bool = False

    @model_validator(mode="after")
    def _rules(self) -> Self:
        problem = cadence_error(self.review_period, self.checkin_cadence, self.feedback_cadence)
        if problem:
            raise ValueError(problem)
        if not self.self_due_days <= self.manager_due_days <= self.ack_due_days:
            raise ValueError("Due dates must run self-score, then manager review, then reply.")
        if any(not -10 <= offset <= 10 for offset in self.reminder_offsets):
            raise ValueError("Reminder offsets must be within 10 working days of the due date.")
        return self
