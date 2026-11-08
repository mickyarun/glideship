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

"""Saving a suggestion run: new suggested goals replace the period's old ones.

A suggestion is only a suggestion: it is never confirmed here, and it
records what it rests on and which version of the role's trends it saw.
Its "why" line can echo text people typed, so it is kept encrypted with
the suggestion's original words.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal import Appraisal
from app.models.appraisal_enums import AppraisalStatus, GoalOrigin, GoalStatus
from app.models.appraisal_goal import AppraisalGoal
from app.repositories.appraisal_cycle import AppraisalCycleRepository
from app.repositories.appraisal_goal import AppraisalGoalRepository
from app.services.appraisals import crypto
from app.services.appraisals.draft_check import DraftUnreadableError
from app.services.appraisals.draft_runner import PERMANENT
from app.services.appraisals.goal_suggest_input import SuggestInput
from app.services.appraisals.goal_suggest_prompt import Suggestion, checked_suggestions
from app.services.claude_runner import ClaudeRunResult

NO_CITED_GOALS = "no_cited_goals"
LOCKED = "goals_locked"
UNREADABLE = "unreadable"


async def _replace(
    db: AsyncSession, appraisal: Appraisal, found: list[Suggestion], data: SuggestInput
) -> None:
    cycle = await AppraisalCycleRepository(db, org_id=appraisal.org_id).get_by_id(
        appraisal.cycle_id
    )
    if cycle is None:
        return
    repo = AppraisalGoalRepository(db, org_id=appraisal.org_id)
    for old in await repo.for_period(appraisal.profile_id, cycle.period_start):
        if old.status is GoalStatus.SUGGESTED:
            old.status = GoalStatus.DISMISSED
    for item in found:
        goal = AppraisalGoal(
            id=uuid.uuid4(),
            org_id=appraisal.org_id,
            profile_id=appraisal.profile_id,
            cycle_id=cycle.id,
            target_period_start=cycle.period_start,
            origin=GoalOrigin.AI_SUGGESTED,
            status=GoalStatus.SUGGESTED,
            suggestion_basis=item.basis,
            suggestion_refs={"cites": item.cites, "trends_version": data.trends_version},
            added_mid_period=False,
        )
        crypto.seal(goal, "title", item.title)
        crypto.seal(goal, "measure", item.measure)
        crypto.seal_json(
            goal, "original", {"title": item.title, "measure": item.measure, "why": item.why}
        )
        db.add(goal)


async def save_suggestions(
    db: AsyncSession, appraisal: Appraisal, data: SuggestInput, result: ClaudeRunResult
) -> tuple[str | None, bool]:
    """Apply a run; its error code (None when saved) and whether that's permanent.

    Goals lock when the review opens and a run takes minutes, so the row is
    checked again here: a run that finishes too late saves nothing.
    """
    if appraisal.status is not AppraisalStatus.ENROLLED:
        return LOCKED, True
    if not result.success:
        code = str(result.error_code.value) if result.error_code else "unknown"
        return code, result.error_code in PERMANENT
    try:
        found = checked_suggestions(result.output, data.known_ids, data.library_only)
    except DraftUnreadableError:
        return UNREADABLE, False
    if not found:
        return NO_CITED_GOALS, False
    await _replace(db, appraisal, found, data)
    return None, False
