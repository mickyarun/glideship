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

"""What the to-do reads share: which appraisals are live, and whose primary manager."""

import uuid
from datetime import date

from sqlalchemy import ColumnElement, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal import Appraisal
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import AppraisalStatus, CycleStatus
from app.models.employee_profile import EmployeeProfile
from app.models.employee_reporting_manager import EmployeeReportingManager


class TodoReads:
    """The filters every to-do query uses, for one org on one day."""

    def __init__(self, db: AsyncSession, *, org_id: uuid.UUID, today: date) -> None:
        """Initialize the repository; ``today`` is the org's date, for who has left."""
        self._db = db
        self._org = org_id
        self._today = today

    def _live(self) -> list[ColumnElement[bool]]:
        """Appraisals still in progress, in cycles that haven't closed, of people still here.

        Every query joins the person's profile; anyone whose leaving date
        has passed drops off everyone's list.
        """
        return [
            Appraisal.org_id == self._org,
            Appraisal.status != AppraisalStatus.WITHDRAWN,
            AppraisalCycle.status != CycleStatus.CLOSED,
            or_(
                EmployeeProfile.date_of_exit.is_(None),
                EmployeeProfile.date_of_exit >= self._today,
            ),
        ]

    def _primary(self, manager_user_id: uuid.UUID) -> ColumnElement[bool]:
        """The caller is the person's primary manager and scores their appraisal."""
        return and_(
            EmployeeReportingManager.org_id == self._org,
            EmployeeReportingManager.profile_id == Appraisal.profile_id,
            EmployeeReportingManager.manager_user_id == manager_user_id,
            EmployeeReportingManager.is_primary.is_(True),
            Appraisal.manager_user_id == manager_user_id,
        )
