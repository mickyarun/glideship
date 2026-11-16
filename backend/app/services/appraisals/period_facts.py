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

"""Facts that belong to a whole review period rather than one month.

Retrospectives and estimate-against-actual on the person's BUDs, and
skills they used for the first time. Gathered by SQL when the review
opens and saved on the appraisal, so the AI summary, the evidence
timeline and the evidence picker all show the same chips.
"""

import uuid
from datetime import UTC
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal import Appraisal
from app.models.appraisal_cycle import AppraisalCycle
from app.models.employee_profile import EmployeeProfile
from app.repositories.work_facts_period import PeriodFactsRepository
from app.services.appraisals.facts import as_ref, bounds
from app.services.appraisals.identity import identity_set


async def gather_period_facts(
    db: AsyncSession, cycle: AppraisalCycle, profile: EmployeeProfile
) -> list[dict[str, Any]]:
    """The person's period facts, as saved fact refs."""
    first, after = bounds(cycle.period_start, cycle.period_end, UTC)
    people: list[uuid.UUID] = await identity_set(db, cycle.org_id, profile.user_id)
    repo = PeriodFactsRepository(db, org_id=cycle.org_id)
    rows = await repo.learnings_and_estimates(people, first, after) + await repo.skills(
        people, first, after
    )
    return [as_ref(row) for row in rows]


async def save_period_facts(
    db: AsyncSession, appraisal: Appraisal, cycle: AppraisalCycle, profile: EmployeeProfile
) -> None:
    """Gather and keep them on the appraisal."""
    appraisal.period_facts = await gather_period_facts(db, cycle, profile)
