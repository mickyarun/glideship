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

"""Assembling a check-in for one viewer: facts they may see, lines, links, goals."""

from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions_people import APPRAISALS_MANAGE
from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import DraftingMode
from app.models.appraisal_goal import AppraisalGoal
from app.models.appraisal_goal_value import AppraisalGoalValue
from app.repositories.appraisal_check_in import AppraisalCheckInRepository
from app.repositories.appraisal_goal import AppraisalGoalRepository
from app.repositories.appraisal_goal_value import AppraisalGoalValueRepository
from app.repositories.appraisal_role_template import AppraisalRoleTemplateRepository
from app.repositories.user import UserRepository
from app.repositories.work_facts_other import readable_boards
from app.schemas.appraisal_check_in import (
    AiLine,
    CheckInPlace,
    CheckInRead,
    FactView,
    GoalPanelItem,
    LinkRead,
)
from app.schemas.appraisal_check_in_note import CheckInNote, FactTag
from app.services.appraisals import audit, crypto
from app.services.appraisals.access import reads_content
from app.services.appraisals.cadence import CADENCE_MONTHS, slices
from app.services.appraisals.check_in_lists import shown_status
from app.services.appraisals.context import Caller, CheckInContext, may_regenerate
from app.services.appraisals.due_dates import is_late, may_change_after_send
from app.services.appraisals.fact_view import board_ids, for_viewer
from app.services.appraisals.feedback_read import shown_on_check_in
from app.services.appraisals.org_clock import org_today


def _place(cycle: AppraisalCycle, start: date) -> CheckInPlace | None:
    """Which check-in of the cycle this is, by its first day."""
    starts = [
        first
        for first, _ in slices(
            cycle.period_start, cycle.period_end, CADENCE_MONTHS[cycle.checkin_cadence]
        )
    ]
    return (
        CheckInPlace(number=starts.index(start) + 1, of=len(starts)) if start in starts else None
    )


async def read_check_in(
    db: AsyncSession, caller: Caller, ctx: CheckInContext, *, log_view: bool = True
) -> CheckInRead:
    """The check-in as ``caller`` may see it.

    Opening it logs a view (someone else's, once a day per appraisal); the
    reply to a save passes ``log_view=False``.
    """
    check_in, profile, org_id = ctx.check_in, ctx.profile, caller.org_id
    is_self = caller.user_id == profile.user_id
    if log_view:
        await audit.record_view(
            db,
            org_id=org_id,
            actor_id=caller.user_id,
            subject_user_id=profile.user_id,
            profile_id=profile.id,
            target=ctx.appraisal.id if ctx.appraisal else check_in.id,
        )
    facts = check_in.fact_refs or []
    boards = (
        set()
        if is_self
        else await readable_boards(db, org_id, caller.user_id, caller.perms, board_ids(facts))
    )
    repo = AppraisalCheckInRepository(db, org_id=org_id)
    values = {
        v.goal_id: v
        for v in await AppraisalGoalValueRepository(db, org_id=org_id).for_check_in(check_in.id)
    }
    period_start = ctx.cycle.period_start if ctx.cycle else check_in.period_start
    goals = await AppraisalGoalRepository(db, org_id=org_id).accepted_for_period(
        profile.id, period_start
    )
    template = None
    if ctx.appraisal and ctx.appraisal.role_template_id:
        template = await AppraisalRoleTemplateRepository(db, org_id=org_id).get_by_id(
            ctx.appraisal.role_template_id
        )
    users = UserRepository(db)
    user = await users.get_by_id_in_org(profile.user_id, org_id)
    manager = (
        await users.get_by_id_in_org(ctx.appraisal.manager_user_id, org_id)
        if ctx.appraisal
        else None
    )
    mode = ctx.appraisal.drafting_mode if ctx.appraisal else DraftingMode.MANUAL
    shown = for_viewer(facts, is_self=is_self, perms=caller.perms, boards=boards)
    # Until it is sent, what the person wrote (lines, links, tags, values and
    # the draft written for them) is theirs alone; the facts stay visible.
    readable = reads_content(caller.user_id, profile.user_id, check_in.sent_at is not None)
    if not readable:
        values = {}
    # The summary is written from every fact; if any is private to this
    # viewer, the prose could name it, so they don't get the summary.
    # A redraft under way or failed keeps showing the lines it would replace.
    drafted = check_in.ai_summary is not None
    hidden = drafted and any(f["private"] for f in shown)
    lines = (
        crypto.unseal_json(check_in, "ai_summary") if drafted and not hidden and readable else None
    )
    today = await org_today(db, org_id)
    return CheckInRead(
        id=check_in.id,
        profile_id=profile.id,
        user_id=profile.user_id,
        person_name=user.name if user else "",
        manager_name=manager.name if manager else None,
        period_start=check_in.period_start,
        period_end=check_in.period_end,
        working_days=check_in.working_days,
        available_days=check_in.available_days,
        status=shown_status(check_in, is_self),
        closed=check_in.closed_at is not None,
        can_edit=ctx.is_open and may_change_after_send(check_in.due_on, check_in.sent_at, today),
        drafting_mode=mode,
        draft_status=check_in.draft_status,
        ai_lines=[AiLine.model_validate(line) for line in lines or []],
        ai_hidden=hidden,
        can_regenerate=may_regenerate(ctx),
        heading_meanings=dict(template.heading_meanings) if template else {},
        facts=[FactView.model_validate(f) for f in shown],
        fact_tags=_tags(check_in.fact_tags or {}) if readable else {},
        note=CheckInNote.model_validate(
            (crypto.unseal_json(check_in, "employee_note") if readable else None) or {}
        ),
        links=[
            LinkRead(
                id=link.id,
                url=crypto.unseal(link, "url") or "",
                title=crypto.unseal(link, "title") or "",
                heading=link.heading,
                goal_id=link.goal_id,
            )
            for link in (await repo.links(check_in.id) if readable else [])
        ],
        goals=[_goal_item(g, values.get(g.id)) for g in goals],
        # Only the person and HR act on a possible duplicate account.
        identity_warnings=(
            check_in.identity_warnings if is_self or caller.perms.has(APPRAISALS_MANAGE) else []
        ),
        appraisal_id=ctx.appraisal.id if ctx.appraisal else None,
        cycle_name=ctx.cycle.name if ctx.cycle else None,
        place=_place(ctx.cycle, check_in.period_start) if ctx.cycle else None,
        feedback=await shown_on_check_in(db, ctx),
        due_on=check_in.due_on,
        sent_at=check_in.sent_at,
        edited_after_send_at=check_in.edited_after_send_at,
        late=is_late(check_in.due_on, check_in.sent_at, today),
        can_send=ctx.is_open and is_self and check_in.sent_at is None,
        content_hidden=not readable,
    )


def _tags(raw: dict[str, Any]) -> dict[str, FactTag]:
    return {key: FactTag.model_validate(value) for key, value in raw.items()}


def _goal_item(goal: AppraisalGoal, value: AppraisalGoalValue | None) -> GoalPanelItem:
    return GoalPanelItem(
        id=goal.id,
        position=goal.position or 0,
        title=crypto.unseal(goal, "title") or "",
        measure=crypto.unseal(goal, "measure"),
        value=crypto.unseal(value, "value") if value else None,
        source_note=crypto.unseal(value, "source_note") if value else None,
        source_url=crypto.unseal(value, "source_url") if value else None,
    )
