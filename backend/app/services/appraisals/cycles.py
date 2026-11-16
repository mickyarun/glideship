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

"""Creating and editing appraisal cycles.

A new cycle copies the org's settings, so later changes to the settings
never move it. Only a draft can be edited or deleted; once it opens, its
dates and rules are what everyone was told.
"""

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import CycleStatus, ReviewPeriod
from app.repositories.appraisal_cycle import AppraisalCycleRepository
from app.schemas.appraisal_cycle import CycleCreate, CycleRead, CycleUpdate
from app.services.appraisals import crypto
from app.services.appraisals.cadence import PERIOD_MONTHS, add_months, cadence_error, period_after
from app.services.appraisals.errors import (
    AppraisalConflictError,
    AppraisalInvalidError,
    AppraisalNotFoundError,
)
from app.services.appraisals.role_templates import ensure_seeded
from app.services.appraisals.settings import load_appraisal_settings


def default_name(review: ReviewPeriod, start: date) -> str:
    """A name like "Q4 2026", "H1 2027" or "2027"."""
    if review is ReviewPeriod.QUARTERLY:
        return f"Q{(start.month - 1) // 3 + 1} {start.year}"
    if review is ReviewPeriod.HALF_YEARLY:
        return f"H{(start.month - 1) // 6 + 1} {start.year}"
    return str(start.year)


def cycle_read(cycle: AppraisalCycle) -> CycleRead:
    """The cycle as the API returns it, with its intro note decrypted."""
    data = {name: getattr(cycle, name) for name in CycleRead.model_fields if name != "intro_note"}
    return CycleRead(**data, intro_note=crypto.unseal(cycle, "intro_note") or "")


def enrolment_cutoff(start: date, end: date) -> date:
    """People who join in the first third of the period are enrolled."""
    return start + timedelta(days=(end - start).days // 3)


async def create_cycle(
    db: AsyncSession, org_id: uuid.UUID, actor_id: uuid.UUID, body: CycleCreate
) -> AppraisalCycle:
    """A draft cycle for the next period, prefilled from the org's settings."""
    settings = await load_appraisal_settings(db, org_id)
    review = body.review_period or settings.review_period
    checkins = body.checkin_cadence or settings.checkin_cadence
    feedback = body.feedback_cadence or settings.feedback_cadence
    problem = cadence_error(review, checkins, feedback)
    if problem:
        raise AppraisalInvalidError(problem)
    repo = AppraisalCycleRepository(db, org_id=org_id)
    if body.period_start is not None:
        start = body.period_start
    else:
        start, _ = period_after(await repo.latest_end(), datetime.now(UTC).date(), review)
    end = add_months(start, PERIOD_MONTHS[review]) - timedelta(days=1)
    self_due = end + timedelta(days=settings.self_due_days)
    cycle = AppraisalCycle(
        id=uuid.uuid4(),
        org_id=org_id,
        name=body.name or default_name(review, start),
        period_start=start,
        period_end=end,
        self_due=self_due,
        manager_due=end + timedelta(days=settings.manager_due_days),
        ack_due=end + timedelta(days=settings.ack_due_days),
        status=CycleStatus.DRAFT,
        review_period=review,
        checkin_cadence=checkins,
        feedback_cadence=feedback,
        feedback_due_days=settings.feedback_due_days,
        reminder_offsets=list(settings.reminder_offsets),
        overdue_nudge=settings.overdue_nudge,
        hr_overdue_list=settings.hr_overdue_list,
        hr_overdue_offset=settings.hr_overdue_offset,
        suggest_goals_on_open=(
            settings.suggest_goals_on_open
            if body.suggest_goals_on_open is None
            else body.suggest_goals_on_open
        ),
        ai_drafting=settings.ai_enabled if body.ai_drafting is None else body.ai_drafting,
        enrolment_cutoff=enrolment_cutoff(start, end),
        scope=body.scope.model_dump(mode="json"),
        template_overrides={k: str(v) for k, v in body.template_overrides.items()},
        created_by=actor_id,
    )
    crypto.seal(cycle, "intro_note", body.intro_note)
    await repo.create(cycle)
    # Readiness matches templates without writing, so they exist from here.
    await ensure_seeded(db, org_id, actor_id)
    return cycle


async def draft_cycle(db: AsyncSession, org_id: uuid.UUID, cycle_id: uuid.UUID) -> AppraisalCycle:
    """The cycle, which must still be a draft."""
    cycle = await AppraisalCycleRepository(db, org_id=org_id).get_by_id(cycle_id)
    if cycle is None:
        raise AppraisalNotFoundError("Cycle not found.")
    if cycle.status is not CycleStatus.DRAFT:
        raise AppraisalConflictError("This cycle has opened; its settings can't change now.")
    return cycle


async def update_cycle(
    db: AsyncSession, org_id: uuid.UUID, cycle_id: uuid.UUID, body: CycleUpdate
) -> AppraisalCycle:
    """Change a draft cycle."""
    cycle = await draft_cycle(db, org_id, cycle_id)
    # A null means "leave it": every column here is required.
    # Python values, not JSON: the cadence rules compare enum members.
    changes = body.model_dump(
        exclude_unset=True,
        exclude_none=True,
        exclude={"intro_note", "scope", "template_overrides"},
    )
    if body.template_overrides is not None:
        cycle.template_overrides = {k: str(v) for k, v in body.template_overrides.items()}
    for field, value in changes.items():
        setattr(cycle, field, value)
    problem = cadence_error(cycle.review_period, cycle.checkin_cadence, cycle.feedback_cadence)
    if problem:
        raise AppraisalInvalidError(problem)
    if body.scope is not None:
        cycle.scope = body.scope.model_dump(mode="json")
    if "intro_note" in body.model_fields_set:
        crypto.seal(cycle, "intro_note", body.intro_note)
    if not cycle.period_end <= cycle.self_due <= cycle.manager_due <= cycle.ack_due:
        raise AppraisalInvalidError(
            "Due dates must run self-score, then manager review, then reply, after the period."
        )
    await db.flush()
    return cycle


async def delete_cycle(db: AsyncSession, org_id: uuid.UUID, cycle_id: uuid.UUID) -> None:
    """Delete a draft cycle."""
    cycle = await draft_cycle(db, org_id, cycle_id)
    await AppraisalCycleRepository(db, org_id=org_id).delete_draft(cycle)


async def close_cycle(db: AsyncSession, org_id: uuid.UUID, cycle_id: uuid.UUID) -> AppraisalCycle:
    """Close a running cycle: its open check-ins close on the next tick, edits stop.

    Feedback still open stays "not done". Nothing is deleted.
    """
    cycle = await AppraisalCycleRepository(db, org_id=org_id).get_by_id(cycle_id)
    if cycle is None:
        raise AppraisalNotFoundError("Cycle not found.")
    if cycle.status is CycleStatus.DRAFT:
        raise AppraisalConflictError("A draft cycle hasn't opened; delete it instead.")
    if cycle.status is not CycleStatus.CLOSED:
        cycle.status = CycleStatus.CLOSED
        await db.flush()
    return cycle
