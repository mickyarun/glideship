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

"""Appraisals for the people in them: the caller's and their team's, and goals.

Rights come from :mod:`app.services.appraisals.access`; anything the
caller may not see answers 404.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._appraisal_deps import get_caller
from app.core.deps import get_db
from app.schemas.appraisal_goal import (
    AppraisalSummary,
    GoalBody,
    GoalEdit,
    GoalOption,
    GoalsRead,
    ReasonBody,
)
from app.services.appraisals import goal_decisions, goal_writes
from app.services.appraisals.appraisal_context import appraisal_context, goal_context
from app.services.appraisals.appraisal_lists import my_appraisals, team_appraisals
from app.services.appraisals.context import Caller
from app.services.appraisals.goal_read import goal_options, list_goals
from app.services.appraisals.goal_suggest_queue import suggest_for

router = APIRouter(tags=["appraisals"])


@router.get("/mine", response_model=list[AppraisalSummary])
async def list_mine(
    caller: Caller = Depends(get_caller), db: AsyncSession = Depends(get_db)
) -> list[AppraisalSummary]:
    """The caller's own appraisals, newest first."""
    return await my_appraisals(db, caller)


@router.get("/team", response_model=list[AppraisalSummary])
async def list_team(
    caller: Caller = Depends(get_caller), db: AsyncSession = Depends(get_db)
) -> list[AppraisalSummary]:
    """The caller's direct reports' appraisals, newest first."""
    return await team_appraisals(db, caller)


@router.get("/{appraisal_id}/goals", response_model=GoalsRead)
async def get_goals(
    appraisal_id: uuid.UUID,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> GoalsRead:
    """The period's goals, with their history and what the caller may do."""
    return await list_goals(db, await appraisal_context(db, caller, appraisal_id))


@router.get("/{appraisal_id}/goal-options", response_model=list[GoalOption])
async def get_goal_options(
    appraisal_id: uuid.UUID,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> list[GoalOption]:
    """Starting points with no AI: the role library and last period's goals."""
    return await goal_options(db, await appraisal_context(db, caller, appraisal_id))


@router.post(
    "/{appraisal_id}/goals", response_model=GoalsRead, status_code=status.HTTP_201_CREATED
)
async def post_goal(
    appraisal_id: uuid.UUID,
    body: GoalBody,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> GoalsRead:
    """The employee proposes a goal; the manager adds a confirmed one."""
    ctx = await appraisal_context(db, caller, appraisal_id)
    await goal_writes.add_goal(db, ctx, body)
    return await list_goals(db, ctx, log_view=False)


@router.patch("/goals/{goal_id}", response_model=GoalsRead)
async def patch_goal(
    goal_id: uuid.UUID,
    body: GoalEdit,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> GoalsRead:
    """Reword a goal (a manager changing a confirmed one gives a reason)."""
    goal, ctx = await goal_context(db, caller, goal_id)
    await goal_writes.edit_goal(db, ctx, goal, body)
    return await list_goals(db, ctx, log_view=False)


@router.delete("/goals/{goal_id}", response_model=GoalsRead)
async def delete_goal(
    goal_id: uuid.UUID,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> GoalsRead:
    """Remove a goal the manager added, before the review opens."""
    goal, ctx = await goal_context(db, caller, goal_id)
    await goal_writes.remove_goal(db, ctx, goal)
    return await list_goals(db, ctx, log_view=False)


@router.post("/goals/{goal_id}/accept", response_model=GoalsRead)
async def accept(
    goal_id: uuid.UUID,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> GoalsRead:
    """Confirm a proposal or take up a suggestion."""
    goal, ctx = await goal_context(db, caller, goal_id)
    await goal_decisions.accept_goal(db, ctx, goal)
    return await list_goals(db, ctx, log_view=False)


@router.post("/goals/{goal_id}/dismiss", response_model=GoalsRead)
async def dismiss(
    goal_id: uuid.UUID,
    body: ReasonBody,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> GoalsRead:
    """Decline a proposal with a reason, withdraw one, or drop a suggestion."""
    goal, ctx = await goal_context(db, caller, goal_id)
    await goal_decisions.dismiss_goal(db, ctx, goal, body)
    return await list_goals(db, ctx, log_view=False)


@router.post("/goals/{goal_id}/ask-reword", response_model=GoalsRead)
async def ask_reword(
    goal_id: uuid.UUID,
    body: ReasonBody,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> GoalsRead:
    """Send a proposal back to the employee with what to change."""
    goal, ctx = await goal_context(db, caller, goal_id)
    await goal_decisions.ask_reword(db, ctx, goal, body)
    return await list_goals(db, ctx, log_view=False)


@router.post("/goals/{goal_id}/suggest-change", response_model=GoalsRead)
async def suggest_change(
    goal_id: uuid.UUID,
    body: GoalEdit,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> GoalsRead:
    """The employee proposes new wording for a confirmed goal."""
    goal, ctx = await goal_context(db, caller, goal_id)
    await goal_writes.suggest_change(db, ctx, goal, body)
    return await list_goals(db, ctx, log_view=False)


@router.post(
    "/{appraisal_id}/suggest-goals",
    response_model=GoalsRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def suggest_goals(
    appraisal_id: uuid.UUID,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> GoalsRead:
    """Ask the AI for suggested goals; they appear when the run finishes."""
    ctx = await appraisal_context(db, caller, appraisal_id)
    await suggest_for(db, ctx)
    await db.refresh(ctx.appraisal)
    return await list_goals(db, ctx, log_view=False)
