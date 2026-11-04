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

"""What the employee adds to their check-in, until it closes.

Only the person themself writes here; a manager's words go into manager
feedback. Every write is checked against the open check-in: tags may
only name facts on it and the period's own goals.
"""

import uuid
from collections.abc import Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_enums import CheckInStatus
from app.models.appraisal_evidence_link import AppraisalEvidenceLink
from app.models.appraisal_goal_value import AppraisalGoalValue
from app.repositories.appraisal_check_in import MAX_LINKS, AppraisalCheckInRepository
from app.repositories.appraisal_goal import AppraisalGoalRepository
from app.schemas.appraisal_check_in import CheckInNote, FactTag, GoalValueIn, LinkCreate
from app.services.appraisals import crypto
from app.services.appraisals.context import CheckInContext
from app.services.appraisals.errors import (
    AppraisalConflictError,
    AppraisalInvalidError,
    AppraisalNotFoundError,
)

CLOSED = "This check-in has closed."


def _require_open(ctx: CheckInContext) -> AppraisalCheckIn:
    if not ctx.is_open:
        raise AppraisalConflictError(CLOSED)
    return ctx.check_in


def _mark_added(check_in: AppraisalCheckIn) -> None:
    if check_in.status is CheckInStatus.OPEN:
        check_in.status = CheckInStatus.EMPLOYEE_ADDED


async def _goal_ids(db: AsyncSession, ctx: CheckInContext) -> set[uuid.UUID]:
    start = ctx.cycle.period_start if ctx.cycle else ctx.check_in.period_start
    goals = await AppraisalGoalRepository(db, org_id=ctx.check_in.org_id).accepted_for_period(
        ctx.profile.id, start
    )
    return {g.id for g in goals}


async def save_note(db: AsyncSession, ctx: CheckInContext, note: CheckInNote) -> None:
    """Replace the employee's lines, blocker and next-month plan."""
    check_in = _require_open(ctx)
    crypto.seal_json(
        check_in, "employee_note", None if note.is_empty else note.model_dump(mode="json")
    )
    if not note.is_empty:
        _mark_added(check_in)
    await db.flush()


async def save_tags(
    db: AsyncSession, ctx: CheckInContext, tags: Mapping[str, FactTag | None]
) -> None:
    """Set which goal (or heading) each fact or link helped; None clears a tag."""
    check_in = _require_open(ctx)
    repo = AppraisalCheckInRepository(db, org_id=check_in.org_id)
    known = {f["id"] for f in check_in.fact_refs or []} | {
        str(link.id) for link in await repo.links(check_in.id)
    }
    goals = await _goal_ids(db, ctx)
    current = dict(check_in.fact_tags or {})
    for item_id, tag in tags.items():
        if item_id not in known:
            raise AppraisalInvalidError("That item isn't on this check-in.")
        if tag is None:
            current.pop(item_id, None)
            continue
        if tag.goal_id is not None and tag.goal_id not in goals:
            raise AppraisalInvalidError("That goal isn't one of this period's goals.")
        current[item_id] = tag.model_dump(mode="json")
    check_in.fact_tags = current
    if current:
        _mark_added(check_in)
    await db.flush()


async def add_link(
    db: AsyncSession, ctx: CheckInContext, actor_id: uuid.UUID, body: LinkCreate
) -> AppraisalEvidenceLink:
    """Add one of up to five links."""
    check_in = _require_open(ctx)
    repo = AppraisalCheckInRepository(db, org_id=check_in.org_id)
    if len(await repo.links(check_in.id)) >= MAX_LINKS:
        raise AppraisalConflictError(f"Up to {MAX_LINKS} links on a check-in.")
    if body.goal_id is not None and body.goal_id not in await _goal_ids(db, ctx):
        raise AppraisalInvalidError("That goal isn't one of this period's goals.")
    link = AppraisalEvidenceLink(
        org_id=check_in.org_id,
        profile_id=ctx.profile.id,
        check_in_id=check_in.id,
        heading=body.heading,
        goal_id=body.goal_id,
        added_by=actor_id,
    )
    crypto.seal(link, "url", str(body.url))
    crypto.seal(link, "title", body.title.strip())
    db.add(link)
    _mark_added(check_in)
    await db.flush()
    return link


async def remove_link(db: AsyncSession, ctx: CheckInContext, link_id: uuid.UUID) -> None:
    """Remove a link, and any tag on it."""
    check_in = _require_open(ctx)
    repo = AppraisalCheckInRepository(db, org_id=check_in.org_id)
    link = await repo.link(link_id)
    if link is None or link.check_in_id != check_in.id:
        raise AppraisalNotFoundError("Link not found.")
    await db.delete(link)
    check_in.fact_tags = {k: v for k, v in (check_in.fact_tags or {}).items() if k != str(link_id)}
    await db.flush()


async def save_goal_value(
    db: AsyncSession,
    ctx: CheckInContext,
    actor_id: uuid.UUID,
    goal_id: uuid.UUID,
    body: GoalValueIn,
) -> None:
    """Set this month's value for one of the period's goals."""
    check_in = _require_open(ctx)
    if goal_id not in await _goal_ids(db, ctx):
        raise AppraisalNotFoundError("Goal not found.")
    repo = AppraisalCheckInRepository(db, org_id=check_in.org_id)
    value = await repo.goal_value(check_in.id, goal_id)
    if value is None:
        value = AppraisalGoalValue(
            org_id=check_in.org_id, goal_id=goal_id, check_in_id=check_in.id
        )
        db.add(value)
    value.reported_by = actor_id
    crypto.seal(value, "value", body.value.strip())
    crypto.seal(value, "source_note", body.source_note.strip())
    crypto.seal(value, "source_url", str(body.source_url) if body.source_url else None)
    _mark_added(check_in)
    await db.flush()
