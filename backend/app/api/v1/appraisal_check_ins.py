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

"""Monthly check-ins: the person's own, and their reports' for managers.

Rights come from :mod:`app.services.appraisals.access`; anything the
caller may not see answers 404.
"""

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._appraisal_deps import get_caller
from app.core.deps import get_db
from app.schemas.appraisal_check_in import (
    CheckInNote,
    CheckInRead,
    CheckInSummary,
    FactTag,
    GoalValueIn,
    LinkCreate,
)
from app.services.appraisals import check_in_writes
from app.services.appraisals.check_in_lists import my_check_ins, team_check_ins
from app.services.appraisals.check_in_read import read_check_in
from app.services.appraisals.context import Caller, CheckInContext, check_in_context
from app.services.appraisals.errors import AppraisalNotFoundError

router = APIRouter(tags=["appraisals"])


async def _own(db: AsyncSession, caller: Caller, check_in_id: uuid.UUID) -> CheckInContext:
    """A check-in the caller may write: only the person themself."""
    ctx = await check_in_context(db, caller, check_in_id)
    if ctx.profile.user_id != caller.user_id:
        # Managers read a report's check-in; they never write in it.
        raise AppraisalNotFoundError("Check-in not found.")
    return ctx


@router.get("/mine", response_model=list[CheckInSummary])
async def list_mine(
    caller: Caller = Depends(get_caller), db: AsyncSession = Depends(get_db)
) -> list[CheckInSummary]:
    """The caller's own check-ins, newest first."""
    return await my_check_ins(db, caller)


@router.get("/team", response_model=list[CheckInSummary])
async def list_team(
    caller: Caller = Depends(get_caller), db: AsyncSession = Depends(get_db)
) -> list[CheckInSummary]:
    """The latest check-ins of the caller's direct reports."""
    return await team_check_ins(db, caller)


@router.get("/{check_in_id}", response_model=CheckInRead)
async def get_check_in(
    check_in_id: uuid.UUID,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> CheckInRead:
    """One check-in, as the caller may see it."""
    ctx = await check_in_context(db, caller, check_in_id)
    return await read_check_in(db, caller, ctx)


@router.post(
    "/{check_in_id}/regenerate",
    response_model=CheckInRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def post_regenerate(
    check_in_id: uuid.UUID,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> CheckInRead:
    """Ask for a fresh AI draft, before the person has added anything."""
    ctx = await check_in_context(db, caller, check_in_id)
    await check_in_writes.regenerate(db, ctx)
    return await read_check_in(db, caller, ctx, log_view=False)


@router.put("/{check_in_id}/note", response_model=CheckInRead)
async def put_note(
    check_in_id: uuid.UUID,
    body: CheckInNote,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> CheckInRead:
    """Save the employee's lines, blocker and plan for next month."""
    ctx = await _own(db, caller, check_in_id)
    await check_in_writes.save_note(db, ctx, body)
    return await read_check_in(db, caller, ctx, log_view=False)


@router.put("/{check_in_id}/fact-tags", response_model=CheckInRead)
async def put_tags(
    check_in_id: uuid.UUID,
    body: dict[str, FactTag | None],
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> CheckInRead:
    """Say which goal (or heading) each fact or link helped."""
    ctx = await _own(db, caller, check_in_id)
    await check_in_writes.save_tags(db, ctx, body)
    return await read_check_in(db, caller, ctx, log_view=False)


@router.post("/{check_in_id}/links", response_model=CheckInRead, status_code=201)
async def post_link(
    check_in_id: uuid.UUID,
    body: LinkCreate,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> CheckInRead:
    """Add a link (up to five)."""
    ctx = await _own(db, caller, check_in_id)
    await check_in_writes.add_link(db, ctx, caller.user_id, body)
    return await read_check_in(db, caller, ctx, log_view=False)


@router.delete("/{check_in_id}/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_link(
    check_in_id: uuid.UUID,
    link_id: uuid.UUID,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Remove a link."""
    ctx = await _own(db, caller, check_in_id)
    await check_in_writes.remove_link(db, ctx, link_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{check_in_id}/goal-values/{goal_id}", response_model=CheckInRead)
async def put_goal_value(
    check_in_id: uuid.UUID,
    goal_id: uuid.UUID,
    body: GoalValueIn,
    caller: Caller = Depends(get_caller),
    db: AsyncSession = Depends(get_db),
) -> CheckInRead:
    """This month's value for one of the period's goals."""
    ctx = await _own(db, caller, check_in_id)
    await check_in_writes.save_goal_value(db, ctx, caller.user_id, goal_id, body)
    return await read_check_in(db, caller, ctx, log_view=False)
