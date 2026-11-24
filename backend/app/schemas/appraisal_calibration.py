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

from pydantic import BaseModel

from app.models.appraisal_enums import AppraisalStatus
from app.schemas.appraisal_review import Band


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
