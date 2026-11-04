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

"""What each kind of AI draft is given, built from the saved records.

Returns None when there is nothing to draft: AI is off for this person, or
there are no facts to write about. The caller then shows the manual view.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal import Appraisal
from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_enums import DraftingMode
from app.models.appraisal_goal import AppraisalGoal
from app.repositories.appraisal import AppraisalRepository
from app.repositories.appraisal_check_in import AppraisalCheckInRepository
from app.repositories.appraisal_cycle import AppraisalCycleRepository
from app.repositories.appraisal_goal import AppraisalGoalRepository
from app.repositories.appraisal_role_template import AppraisalRoleTemplateRepository
from app.repositories.employee_profile import EmployeeProfileRepository
from app.repositories.work_facts_period import PeriodFactsRepository
from app.services.appraisals import crypto
from app.services.appraisals.draft_prompt import (
    BLOCKERS_SECTION,
    CHECK_IN_LINES,
    HEADINGS,
    SUMMARY_LINES,
    check_in_prompt,
    summary_prompt,
)
from app.services.appraisals.facts import as_ref, bounds
from app.services.appraisals.identity import identity_set
from app.services.appraisals.settings import load_appraisal_settings


@dataclass(frozen=True)
class DraftInput:
    """A prompt and what its answer may cite."""

    prompt: str
    known_ids: set[str]
    sections: set[str]
    limit: int


def _goal(goal: AppraisalGoal) -> dict[str, str | None]:
    return {
        "id": str(goal.id),
        "title": crypto.unseal(goal, "title"),
        "measure": crypto.unseal(goal, "measure"),
    }


async def _meanings(db: AsyncSession, appraisal: Appraisal) -> dict[str, str]:
    if appraisal.role_template_id is None:
        return {}
    template = await AppraisalRoleTemplateRepository(db, org_id=appraisal.org_id).get_by_id(
        appraisal.role_template_id
    )
    return dict(template.heading_meanings) if template else {}


async def _ai_allowed(db: AsyncSession, appraisal: Appraisal | None) -> bool:
    if appraisal is None or appraisal.drafting_mode is not DraftingMode.AI:
        return False
    return (await load_appraisal_settings(db, appraisal.org_id)).ai_enabled


async def check_in_input(db: AsyncSession, check_in: AppraisalCheckIn) -> DraftInput | None:
    """The month's prompt, or None when there is nothing to draft."""
    org_id = check_in.org_id
    appraisal = await AppraisalRepository(db, org_id=org_id).for_profile_in_cycle(
        check_in.profile_id, check_in.cycle_id
    )
    facts = check_in.fact_refs or []
    if appraisal is None or not facts or not await _ai_allowed(db, appraisal):
        return None
    cycle = await AppraisalCycleRepository(db, org_id=org_id).get_by_id(check_in.cycle_id)
    start = cycle.period_start if cycle else check_in.period_start
    goals = await AppraisalGoalRepository(db, org_id=org_id).accepted_for_period(
        check_in.profile_id, start
    )
    availability = f"{check_in.available_days} of {check_in.working_days} working days"
    prompt = check_in_prompt(
        facts, [_goal(g) for g in goals], await _meanings(db, appraisal), availability
    )
    return DraftInput(prompt, {f["id"] for f in facts}, set(HEADINGS), CHECK_IN_LINES)


async def _month(db: AsyncSession, check_in: AppraisalCheckIn) -> dict[str, Any]:
    note = crypto.unseal_json(check_in, "employee_note") or {}
    repo = AppraisalCheckInRepository(db, org_id=check_in.org_id)
    return {
        "check_in": str(check_in.id),
        "period_start": check_in.period_start.isoformat(),
        "available_days": str(check_in.available_days),
        "working_days": check_in.working_days,
        "facts": check_in.fact_refs or [],
        "own_lines": note.get("lines", {}),
        "blocking": note.get("blocking", ""),
        "goal_values": [
            {"goal_id": str(v.goal_id), "value": crypto.unseal(v, "value")}
            for v in await repo.goal_values(check_in.id)
        ],
    }


async def summary_input(db: AsyncSession, appraisal: Appraisal) -> DraftInput | None:
    """The period's prompt, or None when there is nothing to draft."""
    org_id = appraisal.org_id
    if not await _ai_allowed(db, appraisal):
        return None
    cycle = await AppraisalCycleRepository(db, org_id=org_id).get_by_id(appraisal.cycle_id)
    profile = await EmployeeProfileRepository(db, org_id=org_id).get_by_id(appraisal.profile_id)
    check_ins = await AppraisalCheckInRepository(db, org_id=org_id).for_person_in_cycle(
        appraisal.profile_id, appraisal.cycle_id
    )
    if cycle is None or profile is None or not check_ins:
        return None
    months = [await _month(db, c) for c in check_ins]
    first, after = bounds(cycle.period_start, cycle.period_end, UTC)
    people: list[uuid.UUID] = await identity_set(db, org_id, profile.user_id)
    repo = PeriodFactsRepository(db, org_id=org_id)
    extra = [
        as_ref(row)
        for row in await repo.learnings_and_estimates(people, first, after)
        + await repo.skills(people, first, after)
    ]
    months.append({"check_in": None, "period_facts": extra})
    goals = await AppraisalGoalRepository(db, org_id=org_id).accepted_for_period(
        appraisal.profile_id, cycle.period_start
    )
    known = {str(c.id) for c in check_ins} | {f["id"] for f in extra}
    known |= {f["id"] for c in check_ins for f in c.fact_refs or []}
    sections = {*HEADINGS, BLOCKERS_SECTION, *(f"goal:{g.id}" for g in goals)}
    prompt = summary_prompt(months, [_goal(g) for g in goals], await _meanings(db, appraisal))
    return DraftInput(prompt, known, sections, SUMMARY_LINES)
