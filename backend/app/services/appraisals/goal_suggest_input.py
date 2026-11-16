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

"""What a goal suggestion run is given, built from the saved records.

Returns None when there is nothing to suggest from, AI is off for the
person, or their goals have locked; the person then picks from the role
library and last period's goals by hand.
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal import Appraisal
from app.models.appraisal_enums import AppraisalStatus, GoalCheck
from app.repositories.appraisal import AppraisalRepository
from app.repositories.appraisal_check_in import AppraisalCheckInRepository
from app.repositories.appraisal_cycle import AppraisalCycleRepository
from app.repositories.appraisal_feedback import AppraisalFeedbackRepository
from app.repositories.appraisal_goal import AppraisalGoalRepository
from app.repositories.appraisal_role_template import AppraisalRoleTemplateRepository
from app.services.appraisals import crypto
from app.services.appraisals.draft_inputs import DraftInput, ai_allowed
from app.services.appraisals.goal_suggest_prompt import MAX_SUGGESTIONS, suggest_prompt

RECENT_CHECK_INS = 3
WATCH = {GoalCheck.AT_RISK.value, GoalCheck.OFF_TRACK.value}


@dataclass(frozen=True)
class SuggestInput(DraftInput):
    """A suggestion prompt, and what saving its answer needs."""

    library_only: bool = True
    trends_version: int | None = None


async def _feedback(db: AsyncSession, appraisal: Appraisal) -> list[dict[str, Any]]:
    """The latest written feedback: its "try next" line and goals at risk."""
    items = await AppraisalFeedbackRepository(db, org_id=appraisal.org_id).for_profiles(
        [appraisal.profile_id]
    )
    for item in items:
        try_next = crypto.unseal(item, "try_note")
        statuses = item.goal_status or {}
        watch = [goal_id for goal_id, v in statuses.items() if v.get("status") in WATCH]
        if try_next or watch:
            return [
                {"id": f"feedback:{item.id}", "try_next": try_next or "", "goals_at_risk": watch}
            ]
    return []


async def _blockers(db: AsyncSession, appraisal: Appraisal) -> list[dict[str, str]]:
    """What the person said was blocking them in their latest check-ins."""
    check_ins = await AppraisalCheckInRepository(db, org_id=appraisal.org_id).for_profiles(
        [appraisal.profile_id]
    )
    out = []
    for check_in in check_ins[:RECENT_CHECK_INS]:
        note = crypto.unseal_json(check_in, "employee_note") or {}
        if str(note.get("blocking", "")).strip():
            out.append({"id": str(check_in.id), "blocking": str(note["blocking"]).strip()})
    return out


async def suggest_input(db: AsyncSession, appraisal: Appraisal) -> SuggestInput | None:
    """The suggestion prompt for the appraisal's period, or None."""
    org_id = appraisal.org_id
    if appraisal.status is not AppraisalStatus.ENROLLED or not await ai_allowed(db, appraisal):
        return None
    cycle = await AppraisalCycleRepository(db, org_id=org_id).get_by_id(appraisal.cycle_id)
    template = (
        await AppraisalRoleTemplateRepository(db, org_id=org_id).get_by_id(
            appraisal.role_template_id
        )
        if appraisal.role_template_id
        else None
    )
    if cycle is None or template is None:
        return None
    library = [
        {"id": f"lib:{i}", **{k: item.get(k, "") for k in ("title", "measure", "measure_source")}}
        for i, item in enumerate(template.goal_library or [])
    ]
    shared = await AppraisalRepository(db, org_id=org_id).shared_cycles(appraisal.profile_id)
    last = [
        {
            "id": f"goal:{g.id}",
            "title": crypto.unseal(g, "title") or "",
            "measure": crypto.unseal(g, "measure") or "",
            # Only a result already shared with the person can shape a goal for them.
            "result": g.final_result.value if g.final_result and g.cycle_id in shared else None,
        }
        for g in await AppraisalGoalRepository(db, org_id=org_id).latest_accepted_before(
            appraisal.profile_id, cycle.period_start
        )
    ]
    # ``trends`` only ever holds an approved list; a draft waits elsewhere.
    approved = template.trends_version > 0
    trends = [{"id": f"trend:{t['id']}", "text": t["text"]} for t in template.trends or []]
    feedback, blockers = await _feedback(db, appraisal), await _blockers(db, appraisal)
    if not (library or last or feedback or blockers or trends):
        return None
    payload = {
        "role": template.name,
        "library": library,
        "last_period": last,
        "feedback": feedback,
        "blockers": blockers,
        "trends": trends,
    }
    known = {
        str(item["id"]) for part in payload.values() if isinstance(part, list) for item in part
    }
    library_only = not (last or feedback or blockers)
    return SuggestInput(
        prompt=suggest_prompt(payload, library_only),
        known_ids=known,
        sections=set(),
        limit=MAX_SUGGESTIONS,
        library_only=library_only,
        trends_version=template.trends_version if approved else None,
    )
