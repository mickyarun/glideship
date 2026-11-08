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

"""The growth conversation for one shared review: strength, focus, next goals.

Rights come from :mod:`app.services.appraisals.access`; anything the
caller may not see answers 404. Each route answers with the review.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._appraisal_deps import get_caller
from app.core.deps import get_db
from app.schemas.appraisal_goal import GoalBody
from app.schemas.appraisal_growth import GrowthBody
from app.schemas.appraisal_review import AppraisalRead
from app.services.appraisals import growth
from app.services.appraisals.appraisal_context import appraisal_context
from app.services.appraisals.context import Caller
from app.services.appraisals.review_read import read_review

router = APIRouter(tags=["appraisals"])


@router.put("/{appraisal_id}/growth", response_model=AppraisalRead)
async def put_growth(
    appraisal_id: uuid.UUID,
    body: GrowthBody,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> AppraisalRead:
    """Save the strength to use more and the thing to work on."""
    ctx = await appraisal_context(db, caller, appraisal_id)
    await growth.save_growth(db, ctx, body)
    return await read_review(db, caller, ctx, log_view=False)


@router.post(
    "/{appraisal_id}/next-goals", response_model=AppraisalRead, status_code=status.HTTP_201_CREATED
)
async def post_next_goal(
    appraisal_id: uuid.UUID,
    body: GoalBody,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> AppraisalRead:
    """Add a goal for the next period: confirmed by the manager, proposed by the employee."""
    ctx = await appraisal_context(db, caller, appraisal_id)
    await growth.add_next_goal(db, ctx, body)
    return await read_review(db, caller, ctx, log_view=False)


@router.post("/{appraisal_id}/next-goals/{goal_id}/accept", response_model=AppraisalRead)
async def accept_next_goal(
    appraisal_id: uuid.UUID,
    goal_id: uuid.UUID,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> AppraisalRead:
    """The manager confirms a proposed next-period goal."""
    ctx = await appraisal_context(db, caller, appraisal_id)
    await growth.accept_next_goal(db, ctx, goal_id)
    return await read_review(db, caller, ctx, log_view=False)


@router.delete("/{appraisal_id}/next-goals/{goal_id}", response_model=AppraisalRead)
async def remove_next_goal(
    appraisal_id: uuid.UUID,
    goal_id: uuid.UUID,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> AppraisalRead:
    """Take a next-period goal back before it locks."""
    ctx = await appraisal_context(db, caller, appraisal_id)
    await growth.remove_next_goal(db, ctx, goal_id)
    return await read_review(db, caller, ctx, log_view=False)
