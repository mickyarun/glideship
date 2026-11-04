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

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions_people import APPRAISALS_MANAGE
from app.models.appraisal_enums import DraftingMode
from app.models.appraisal_goal import AppraisalGoal
from app.models.appraisal_goal_value import AppraisalGoalValue
from app.repositories.appraisal_check_in import AppraisalCheckInRepository
from app.repositories.appraisal_goal import AppraisalGoalRepository
from app.repositories.appraisal_role_template import AppraisalRoleTemplateRepository
from app.repositories.user import UserRepository
from app.repositories.work_facts_other import readable_boards
from app.schemas.appraisal_check_in import (
    AiLine,
    CheckInNote,
    CheckInRead,
    FactTag,
    FactView,
    GoalPanelItem,
    LinkRead,
)
from app.services.appraisals import audit, crypto
from app.services.appraisals.context import Caller, CheckInContext, may_regenerate
from app.services.appraisals.fact_view import board_ids, for_viewer


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
    values = {v.goal_id: v for v in await repo.goal_values(check_in.id)}
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
    # The summary is written from every fact; if any is private to this
    # viewer, the prose could name it, so they don't get the summary.
    # A redraft under way or failed keeps showing the lines it would replace.
    drafted = check_in.ai_summary is not None
    hidden = drafted and any(f["private"] for f in shown)
    lines = crypto.unseal_json(check_in, "ai_summary") if drafted and not hidden else None
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
        status=check_in.status,
        closed=check_in.closed_at is not None,
        can_edit=ctx.is_open,
        drafting_mode=mode,
        draft_status=check_in.draft_status,
        ai_lines=[AiLine.model_validate(line) for line in lines or []],
        ai_hidden=hidden,
        can_regenerate=may_regenerate(ctx),
        heading_meanings=dict(template.heading_meanings) if template else {},
        facts=[FactView.model_validate(f) for f in shown],
        fact_tags=_tags(check_in.fact_tags or {}),
        note=CheckInNote.model_validate(crypto.unseal_json(check_in, "employee_note") or {}),
        links=[
            LinkRead(
                id=link.id,
                url=crypto.unseal(link, "url") or "",
                title=crypto.unseal(link, "title") or "",
                heading=link.heading,
                goal_id=link.goal_id,
            )
            for link in await repo.links(check_in.id)
        ],
        goals=[_goal_item(g, values.get(g.id)) for g in goals],
        # Only the person and HR act on a possible duplicate account.
        identity_warnings=(
            check_in.identity_warnings if is_self or caller.perms.has(APPRAISALS_MANAGE) else []
        ),
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
