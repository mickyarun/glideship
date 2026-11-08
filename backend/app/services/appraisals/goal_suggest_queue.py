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

"""Asking for suggested goals: for one person, a whole cycle, or when it opens.

Only queues the run; the draft sweeper does the work, so a request
survives a restart. Manual mode has no suggestions: there the person
picks from the role library and last period's goals.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_enums import DraftingMode
from app.repositories.appraisal import AppraisalRepository
from app.services.appraisals.appraisal_context import AppraisalContext
from app.services.appraisals.errors import AppraisalConflictError
from app.services.appraisals.goal_writes import goal_rights


async def suggest_for(db: AsyncSession, ctx: AppraisalContext) -> None:
    """Queue suggestions for one person; the employee or their manager asks."""
    rights = goal_rights(ctx)
    if not (rights.employee or rights.manager):
        raise AppraisalConflictError("Goals can't be suggested now.")
    if ctx.appraisal.drafting_mode is not DraftingMode.AI:
        raise AppraisalConflictError("AI suggestions are off; pick from the role library instead.")
    repo = AppraisalRepository(db, org_id=ctx.cycle.org_id)
    await repo.queue_suggestions(ctx.cycle.id, [ctx.appraisal.id])


async def suggest_for_cycle(db: AsyncSession, org_id: uuid.UUID, cycle_id: uuid.UUID) -> int:
    """Queue suggestions for everyone in the cycle whose goals are still open."""
    return await AppraisalRepository(db, org_id=org_id).queue_suggestions(cycle_id)
