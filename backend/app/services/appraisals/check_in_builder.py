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

"""Creating one person's check-in for a period, and refreshing it until it closes.

The row and its fact list are written in one go, before any AI is
involved, so a check-in is always usable. An AI-mode check-in is marked
``pending`` for the draft sweeper; a manual one never is.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime, tzinfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal import Appraisal
from app.models.appraisal_check_in import AppraisalCheckIn
from app.models.appraisal_enums import DraftingMode, DraftStatus, FactSource
from app.models.appraisal_role_template import AppraisalRoleTemplate
from app.models.employee_profile import EmployeeProfile
from app.repositories.appraisal_identity import LooseAccount
from app.repositories.user import UserRepository
from app.services.appraisals.availability import availability_for
from app.services.appraisals.facts import gather
from app.services.appraisals.identity import Person, identity_set, possible_duplicates, warning

# What a person with no role template is shown.
FALLBACK_SOURCES = (FactSource.BOARD_CARDS, FactSource.BUGS)


async def _fill(
    db: AsyncSession,
    check_in: AppraisalCheckIn,
    profile: EmployeeProfile,
    template: AppraisalRoleTemplate | None,
    loose: Sequence[LooseAccount],
    zone: tzinfo,
) -> None:
    """Work out availability, identity warnings and the fact list."""
    org_id = check_in.org_id
    available = await availability_for(
        db, org_id, profile, check_in.period_start, check_in.period_end
    )
    check_in.working_days = available.working_days
    check_in.available_days = available.available_days
    user = await UserRepository(db).get_by_id_in_org(profile.user_id, org_id)
    if user is not None:
        person = Person(user.id, user.name, user.email, user.github_username)
        check_in.identity_warnings = [warning(a) for a in possible_duplicates(person, loose)]
    sources = template.fact_sources if template else FALLBACK_SOURCES
    check_in.facts_at = datetime.now(UTC)
    check_in.fact_refs = await gather(
        db,
        org_id,
        await identity_set(db, org_id, profile.user_id),
        sources,
        check_in.period_start,
        check_in.period_end,
        zone,
    )


async def create_check_in(
    db: AsyncSession,
    appraisal: Appraisal,
    profile: EmployeeProfile,
    template: AppraisalRoleTemplate | None,
    period: tuple[date, date],
    loose: Sequence[LooseAccount],
    zone: tzinfo,
) -> AppraisalCheckIn:
    """A new check-in for one period, facts included."""
    check_in = AppraisalCheckIn(
        id=uuid.uuid4(),
        org_id=appraisal.org_id,
        profile_id=profile.id,
        cycle_id=appraisal.cycle_id,
        period_start=period[0],
        period_end=period[1],
        draft_status=(
            DraftStatus.PENDING if appraisal.drafting_mode is DraftingMode.AI else DraftStatus.NONE
        ),
    )
    await _fill(db, check_in, profile, template, loose, zone)
    db.add(check_in)
    await db.flush()
    return check_in


async def refresh_check_in(
    db: AsyncSession,
    check_in: AppraisalCheckIn,
    profile: EmployeeProfile,
    template: AppraisalRoleTemplate | None,
    loose: Sequence[LooseAccount],
    zone: tzinfo,
) -> None:
    """Re-gather an open check-in, keeping what the person wrote and tagged.

    Tags on facts that have since dropped out (a card reopened) are kept
    but no longer shown, so they come back if the card is done again.
    """
    if check_in.closed_at is not None:
        return
    await _fill(db, check_in, profile, template, loose, zone)
    await db.flush()
