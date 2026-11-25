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

"""HR's fairness check over the API: bands and states per manager and person, no reasons."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.appraisal_enums import AppraisalStatus
from app.schemas.appraisal_review import Band


class CalibrationPerson(BaseModel):
    """One reviewed person in calibration: bands and states, no reasons."""

    appraisal_id: uuid.UUID
    name: str
    manager_user_id: uuid.UUID
    manager_name: str
    status: AppraisalStatus
    self_band: Band | None
    final_band: Band | None
    gap: bool
    # The manager flagged a performance concern in the part only HR reads.
    concern: bool = False
    feedback: int
    feedback_done: int
    # Flagged (a big gap, a concern, or a team that rates high) and not yet
    # found fair: left out of sharing everything that's ready.
    held: bool = False
    looks_fair_at: datetime | None = None
    looks_fair_by_name: str = ""


class CalibrationTeam(BaseModel):
    """One manager's figures."""

    manager_user_id: uuid.UUID
    manager_name: str
    # Reviews sent to HR, out of everyone the manager scores (withdrawn left out).
    people: int
    total: int = 0
    bands: dict[int, int]
    agreement: float | None
    gaps: int
    flag: str | None
    # Exceeded bands among this team's reviews, and among every other team's.
    high: int = 0
    others_high: int = 0
    others_people: int = 0
    rates_high: bool = False
    # Would rate high, but no other manager's reviews are in to compare with yet.
    waiting: bool = False


class LooksFairBody(BaseModel):
    """Flagged results HR looked at and found fair."""

    appraisal_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)


class Calibration(BaseModel):
    """The cycle's calibration view."""

    teams: list[CalibrationTeam]
    people: list[CalibrationPerson]
