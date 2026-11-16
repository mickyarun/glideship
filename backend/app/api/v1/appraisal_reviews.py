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

"""The end-of-period review for the people in it: read, self-score, manager review,
HR's send-back and share, and the employee's acknowledgement.

Rights come from :mod:`app.services.appraisals.access`; anything the
caller may not see answers 404. Mounted after the routers whose fixed
paths (``/mine``, ``/team``, ``/settings``) share this prefix.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._appraisal_deps import get_caller
from app.core.deps import get_db
from app.schemas.appraisal_review import AppraisalRead, ManagerBody, NoteBody, ReplyBody, SelfBody
from app.services.appraisals import manager_review, self_review, sharing
from app.services.appraisals.appraisal_context import appraisal_context
from app.services.appraisals.context import Caller
from app.services.appraisals.review_read import read_review

router = APIRouter(tags=["appraisals"])


@router.get("/{appraisal_id}", response_model=AppraisalRead)
async def get_appraisal(
    appraisal_id: uuid.UUID,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> AppraisalRead:
    """The review, evidence first, as the caller may see it."""
    return await read_review(db, caller, await appraisal_context(db, caller, appraisal_id))


@router.put("/{appraisal_id}/self", response_model=AppraisalRead)
async def put_self(
    appraisal_id: uuid.UUID,
    body: SelfBody,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> AppraisalRead:
    """Save the self-review so far."""
    ctx = await appraisal_context(db, caller, appraisal_id)
    await self_review.save_self(db, ctx, body)
    return await read_review(db, caller, ctx, log_view=False)


@router.post("/{appraisal_id}/self/submit", response_model=AppraisalRead)
async def submit_self(
    appraisal_id: uuid.UUID,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> AppraisalRead:
    """Hand the self-review to the manager."""
    ctx = await appraisal_context(db, caller, appraisal_id)
    await self_review.submit_self(db, ctx)
    return await read_review(db, caller, ctx, log_view=False)


@router.put("/{appraisal_id}/manager", response_model=AppraisalRead)
async def put_manager(
    appraisal_id: uuid.UUID,
    body: ManagerBody,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> AppraisalRead:
    """Save the manager's review so far."""
    ctx = await appraisal_context(db, caller, appraisal_id)
    await manager_review.save_manager(db, ctx, body)
    return await read_review(db, caller, ctx, log_view=False)


@router.post("/{appraisal_id}/manager/submit", response_model=AppraisalRead)
async def submit_manager(
    appraisal_id: uuid.UUID,
    body: ManagerBody,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> AppraisalRead:
    """Check the manager's review and send it to HR."""
    ctx = await appraisal_context(db, caller, appraisal_id)
    await manager_review.send_manager(db, ctx, body)
    return await read_review(db, caller, ctx, log_view=False)


@router.post("/{appraisal_id}/send-back", response_model=AppraisalRead)
async def send_back(
    appraisal_id: uuid.UUID,
    body: NoteBody,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> AppraisalRead:
    """HR returns the review to the manager with a note."""
    ctx = await appraisal_context(db, caller, appraisal_id)
    await sharing.send_back(db, ctx, body.note)
    return await read_review(db, caller, ctx, log_view=False)


@router.post("/{appraisal_id}/share", response_model=AppraisalRead)
async def share(
    appraisal_id: uuid.UUID,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> AppraisalRead:
    """HR shows the result to the employee."""
    ctx = await appraisal_context(db, caller, appraisal_id)
    await sharing.share(db, ctx)
    return await read_review(db, caller, ctx, log_view=False)


@router.post("/{appraisal_id}/acknowledge", response_model=AppraisalRead)
async def acknowledge(
    appraisal_id: uuid.UUID,
    body: ReplyBody,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> AppraisalRead:
    """The employee has read their result, with an optional reply."""
    ctx = await appraisal_context(db, caller, appraisal_id)
    await sharing.acknowledge(db, ctx, body.reply)
    return await read_review(db, caller, ctx, log_view=False)
