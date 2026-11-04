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

"""Rows for the appraisal integration tests: a cycle and one appraisal."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal import Appraisal
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import (
    CheckInCadence,
    DraftingMode,
    FeedbackCadence,
    ReviewPeriod,
)
from app.repositories.employee_profile import EmployeeProfileRepository
from tests.integration.leave_support import Factory, report_to, setup_org


def cycle_row(org_id: uuid.UUID, **overrides: Any) -> AppraisalCycle:
    """A valid quarterly cycle for Q4 2026; override any column."""
    values: dict[str, Any] = {
        "org_id": org_id,
        "name": "Q4 2026",
        "period_start": date(2026, 10, 1),
        "period_end": date(2026, 12, 31),
        "self_due": date(2027, 1, 7),
        "manager_due": date(2027, 1, 14),
        "review_period": ReviewPeriod.QUARTERLY,
        "checkin_cadence": CheckInCadence.MONTHLY,
        "feedback_cadence": FeedbackCadence.MONTHLY,
        "feedback_due_days": 10,
        "reminder_offsets": [-3, 0, 2],
        "overdue_nudge": True,
        "hr_overdue_list": True,
        "hr_overdue_offset": 3,
        "suggest_goals_on_open": False,
        "ai_drafting": False,
        "enrolment_cutoff": date(2026, 10, 31),
    }
    values.update(overrides)
    return AppraisalCycle(**values)


@dataclass(frozen=True)
class AppraisalTeam:
    """An org with an employee, their primary manager and a spare member."""

    org: uuid.UUID
    employee: uuid.UUID
    manager: uuid.UUID
    other: uuid.UUID
    profile_id: uuid.UUID
    cycle_id: uuid.UUID
    appraisal_id: uuid.UUID


async def appraisal_team(factory: Factory) -> AppraisalTeam:
    """Seed an org, a draft cycle and the employee's appraisal in it."""
    org, (emp, mgr, other), _ = await setup_org(factory, "Priya", "Ravi", "Meena")
    await report_to(factory, org, emp, mgr)
    async with factory() as db:
        profile = await EmployeeProfileRepository(db, org_id=org).get_by_user(emp)
        assert profile is not None
        cycle = cycle_row(org)
        db.add(cycle)
        await db.flush()
        appraisal = Appraisal(
            org_id=org,
            cycle_id=cycle.id,
            profile_id=profile.id,
            manager_user_id=mgr,
            drafting_mode=DraftingMode.MANUAL,
        )
        db.add(appraisal)
        await db.commit()
        return AppraisalTeam(org, emp, mgr, other, profile.id, cycle.id, appraisal.id)


async def add_and_commit(db: AsyncSession, row: object) -> None:
    """Insert one row and commit, so constraint errors surface here."""
    db.add(row)
    await db.commit()
