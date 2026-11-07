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

"""The facts behind the intro guide, for anyone in the org."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions_people import APPRAISALS_MANAGE
from app.repositories.appraisal import AppraisalRepository
from app.repositories.appraisal_cycle import RUNNING, AppraisalCycleRepository
from app.schemas.appraisal_guide import GuideRead
from app.services.appraisals import crypto
from app.services.appraisals.context import Caller
from app.services.appraisals.settings import load_appraisal_settings


async def guide(db: AsyncSession, caller: Caller) -> GuideRead:
    """The running cycle's rules and HR's note, else the org's settings."""
    recent = await AppraisalCycleRepository(db, org_id=caller.org_id).list_recent(limit=5)
    cycle = next((c for c in recent if c.status in RUNNING), None)
    is_manager = bool(
        await AppraisalRepository(db, org_id=caller.org_id).report_profile_ids(caller.user_id)
    )
    is_hr = caller.perms.has(APPRAISALS_MANAGE)
    if cycle is not None:
        return GuideRead(
            cycle_name=cycle.name,
            review_period=cycle.review_period,
            checkin_cadence=cycle.checkin_cadence,
            feedback_cadence=cycle.feedback_cadence,
            period_start=cycle.period_start,
            period_end=cycle.period_end,
            self_due=cycle.self_due,
            manager_due=cycle.manager_due,
            ack_due=cycle.ack_due,
            feedback_due_days=cycle.feedback_due_days,
            reminder_offsets=list(cycle.reminder_offsets or []),
            ai_drafting=cycle.ai_drafting,
            intro_note=crypto.unseal(cycle, "intro_note") or "",
            is_manager=is_manager,
            is_hr=is_hr,
        )
    settings = await load_appraisal_settings(db, caller.org_id)
    return GuideRead(
        cycle_name=None,
        review_period=settings.review_period,
        checkin_cadence=settings.checkin_cadence,
        feedback_cadence=settings.feedback_cadence,
        period_start=None,
        period_end=None,
        self_due=None,
        manager_due=None,
        ack_due=None,
        feedback_due_days=settings.feedback_due_days,
        reminder_offsets=list(settings.reminder_offsets),
        ai_drafting=settings.ai_enabled,
        intro_note="",
        is_manager=is_manager,
        is_hr=is_hr,
    )
