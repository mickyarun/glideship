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

"""A person's goals for one period as the caller may see them, and goal options."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_enums import GoalRevisionKind, GoalStatus
from app.models.appraisal_goal import AppraisalGoal
from app.repositories.appraisal_goal import AppraisalGoalRepository
from app.repositories.appraisal_role_template import AppraisalRoleTemplateRepository
from app.repositories.user import UserRepository
from app.schemas.appraisal_goal import (
    GoalActionsRead,
    GoalOption,
    GoalRead,
    GoalsRead,
    GoalWords,
    HistoryRead,
)
from app.services.appraisals import crypto, goal_history
from app.services.appraisals.appraisal_context import AppraisalContext
from app.services.appraisals.goal_history import GoalText, HistoryEntry
from app.services.appraisals.goal_rules import MAX_GOALS, actions, is_locked
from app.services.appraisals.goal_writes import goal_rights


def _words(text: GoalText | None) -> GoalWords | None:
    return GoalWords(title=text.title, measure=text.measure) if text else None


def _goal(
    goal: AppraisalGoal,
    history: list[HistoryEntry],
    names: dict[uuid.UUID, str],
    pending: set[str],
    rights_ctx: AppraisalContext,
) -> GoalRead:
    allowed = actions(goal, goal_rights(rights_ctx), pending_change=str(goal.id) in pending)
    rewords = [h for h in history if h.kind is GoalRevisionKind.REWORD_ASKED]
    replaces = goal.suggestion_refs.get("replaces")
    return GoalRead(
        id=goal.id,
        position=goal.position,
        title=crypto.unseal(goal, "title") or "",
        measure=crypto.unseal(goal, "measure") or "",
        origin=goal.origin,
        status=goal.status,
        suggestion_basis=goal.suggestion_basis,
        proposed_by_name=names.get(goal.proposed_by, "") if goal.proposed_by else "",
        added_mid_period=goal.added_mid_period,
        created_at=goal.created_at,
        replaces=uuid.UUID(replaces) if replaces else None,
        dismiss_reason=crypto.unseal(goal, "dismiss_reason"),
        reword_note=rewords[-1].reason if rewords else None,
        history=[
            HistoryRead(
                kind=h.kind,
                by_name=names.get(h.changed_by, ""),
                at=h.at,
                before=_words(h.before),
                after=_words(h.after),
                reason=h.reason,
            )
            for h in history
        ],
        actions=GoalActionsRead(**allowed.__dict__),
    )


async def list_goals(db: AsyncSession, ctx: AppraisalContext) -> GoalsRead:
    """Every goal for the period, confirmed first, with history and what the caller may do."""
    repo = AppraisalGoalRepository(db, org_id=ctx.cycle.org_id)
    goals = await repo.for_period(ctx.profile.id, ctx.cycle.period_start)
    by_goal: dict[uuid.UUID, list[HistoryEntry]] = {g.id: [] for g in goals}
    for revision in await repo.revisions(list(by_goal)):
        by_goal[revision.goal_id].append(goal_history.read(revision))
    people = {g.proposed_by for g in goals if g.proposed_by} | {
        h.changed_by for entries in by_goal.values() for h in entries
    }
    people |= {ctx.profile.user_id, ctx.appraisal.manager_user_id}
    names = {u.id: u.name for u in await UserRepository(db).get_many_by_ids(list(people))}
    pending = {
        str(g.suggestion_refs.get("replaces"))
        for g in goals
        if g.status is GoalStatus.PROPOSED and g.suggestion_refs.get("replaces")
    }
    order = {GoalStatus.ACCEPTED: 0, GoalStatus.PROPOSED: 1, GoalStatus.SUGGESTED: 2}
    goals.sort(key=lambda g: (order.get(g.status, 3), g.position or 0, g.created_at))
    rights = goal_rights(ctx)
    return GoalsRead(
        appraisal_id=ctx.appraisal.id,
        person_name=names.get(ctx.profile.user_id, ""),
        manager_name=names.get(ctx.appraisal.manager_user_id),
        period_start=ctx.cycle.period_start,
        period_end=ctx.cycle.period_end,
        locked=is_locked(ctx.appraisal, ctx.cycle),
        limit=MAX_GOALS,
        accepted=sum(g.status is GoalStatus.ACCEPTED for g in goals),
        can_propose=rights.employee,
        can_add=rights.manager,
        goals=[_goal(g, by_goal[g.id], names, pending, ctx) for g in goals],
    )


async def goal_options(db: AsyncSession, ctx: AppraisalContext) -> list[GoalOption]:
    """The role library and last period's goals to carry over; no AI involved."""
    options: list[GoalOption] = []
    repo = AppraisalGoalRepository(db, org_id=ctx.cycle.org_id)
    for goal in await repo.latest_accepted_before(ctx.profile.id, ctx.cycle.period_start):
        options.append(
            GoalOption(
                source="last_period",
                title=crypto.unseal(goal, "title") or "",
                measure=crypto.unseal(goal, "measure") or "",
                measure_source="",
                last_result=goal.final_result,
            )
        )
    template_id = ctx.appraisal.role_template_id
    template = (
        await AppraisalRoleTemplateRepository(db, org_id=ctx.cycle.org_id).get_by_id(template_id)
        if template_id
        else None
    )
    for item in (template.goal_library if template else []) or []:
        options.append(
            GoalOption(
                source="role_library",
                title=str(item.get("title", "")),
                measure=str(item.get("measure", "")),
                measure_source=str(item.get("measure_source", "")),
            )
        )
    return options
