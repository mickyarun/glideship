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

"""The intro guide's facts, worded on screen from the org's own settings."""

from datetime import date

from pydantic import BaseModel

from app.models.appraisal_enums import CheckInCadence, FeedbackCadence, ReviewPeriod


class GuideRead(BaseModel):
    """The running cycle's rules, or the org's settings when none is running."""

    cycle_name: str | None
    review_period: ReviewPeriod
    checkin_cadence: CheckInCadence
    feedback_cadence: FeedbackCadence
    period_start: date | None
    period_end: date | None
    self_due: date | None
    manager_due: date | None
    ack_due: date | None
    feedback_due_days: int
    reminder_offsets: list[int]
    ai_drafting: bool
    intro_note: str
    # Which audience tabs open first; every tab stays readable.
    is_manager: bool
    is_hr: bool
