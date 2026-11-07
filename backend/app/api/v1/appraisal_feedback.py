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

"""Manager feedback: the manager's team list, one item, writing and finishing it.

Rights come from :mod:`app.services.appraisals.access`; anything the
caller may not see answers 404.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._appraisal_deps import get_caller
from app.core.deps import get_db
from app.schemas.appraisal_feedback import FeedbackBody, FeedbackRead, FeedbackRow
from app.services.appraisals.context import Caller
from app.services.appraisals.feedback import feedback_context, mark_done, save_feedback
from app.services.appraisals.feedback_read import read_feedback, team_feedback

router = APIRouter(tags=["appraisals"])


@router.get("/team", response_model=list[FeedbackRow])
async def list_team(
    caller: Caller = Depends(get_caller), db: AsyncSession = Depends(get_db)
) -> list[FeedbackRow]:
    """The feedback items the caller writes for their reports."""
    return await team_feedback(db, caller)


@router.get("/{feedback_id}", response_model=FeedbackRead)
async def get_feedback(
    feedback_id: uuid.UUID,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> FeedbackRead:
    """One feedback item."""
    ctx = await feedback_context(db, caller, feedback_id)
    return await read_feedback(db, caller, ctx)


@router.put("/{feedback_id}", response_model=FeedbackRead)
async def put_feedback(
    feedback_id: uuid.UUID,
    body: FeedbackBody,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> FeedbackRead:
    """Save the manager's lines and goal statuses; the employee sees them at once."""
    ctx = await feedback_context(db, caller, feedback_id)
    await save_feedback(db, caller, ctx, body)
    return await read_feedback(db, caller, ctx, log_view=False)


@router.post("/{feedback_id}/done", response_model=FeedbackRead)
async def post_done(
    feedback_id: uuid.UUID,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> FeedbackRead:
    """Mark the item done."""
    ctx = await feedback_context(db, caller, feedback_id)
    await mark_done(db, caller, ctx)
    return await read_feedback(db, caller, ctx, log_view=False)
