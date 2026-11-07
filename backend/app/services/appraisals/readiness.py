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

"""What HR should look at before a cycle opens (no AI, no writes).

Who is in scope, who can't be enrolled for want of a primary manager, who
would fall back to the general template, whose work may sit on an
unmerged account, and whether drafts will be AI or manual and why.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appraisal_cycle import AppraisalCycle
from app.models.appraisal_enums import CycleStatus, DraftingMode
from app.repositories.appraisal import AppraisalRepository
from app.repositories.appraisal_identity import AppraisalIdentityRepository
from app.repositories.appraisal_role_template import AppraisalRoleTemplateRepository
from app.repositories.employee_reporting_manager import EmployeeReportingManagerRepository
from app.repositories.organization import OrganizationRepository
from app.repositories.user import UserRepository
from app.schemas.appraisal_cycle import IdentityFlag, PersonRef, Readiness
from app.services.appraisals.draft_runner import provider_refusal
from app.services.appraisals.enrolment import in_scope, primary_link
from app.services.appraisals.identity import Person, possible_duplicates
from app.services.appraisals.role_templates import match_template
from app.services.appraisals.settings import load_appraisal_settings


async def _ai_note(db: AsyncSession, cycle: AppraisalCycle) -> str | None:
    """Why this cycle's drafts would be manual for everyone, or None."""
    if not (await load_appraisal_settings(db, cycle.org_id)).ai_enabled:
        return "AI drafting is off in the appraisal settings."
    if not cycle.ai_drafting:
        return "AI drafting is off for this cycle."
    org = await OrganizationRepository(db).get_by_id(cycle.org_id)
    return provider_refusal(org.ai_provider if org else None)


async def readiness(db: AsyncSession, cycle: AppraisalCycle) -> Readiness:
    """The cycle's readiness, worked out from today's people and settings.

    For a cycle that has opened, it describes who would be enrolled now.
    """
    org_id = cycle.org_id
    # Seeded when the cycle was created; a read never writes.
    templates = await AppraisalRoleTemplateRepository(db, org_id=org_id).list_for_org()
    exclude: list[uuid.UUID] = []
    if cycle.status is not CycleStatus.DRAFT:
        exclude = [
            a.profile_id for a in await AppraisalRepository(db, org_id=org_id).for_cycle(cycle.id)
        ]
    profiles = await AppraisalRepository(db, org_id=org_id).enrollable_profiles(
        cycle.enrolment_cutoff, exclude=exclude
    )
    links = await EmployeeReportingManagerRepository(db, org_id=org_id).list_for_profiles(
        [p.id for p in profiles]
    )
    users = {
        u.id: u for u in await UserRepository(db).get_many_by_ids([p.user_id for p in profiles])
    }
    loose = await AppraisalIdentityRepository(db, org_id=org_id).accounts_without_profile()
    count = 0
    no_manager: list[PersonRef] = []
    no_template: list[PersonRef] = []
    identity: list[IdentityFlag] = []
    for profile in profiles:
        template = match_template(
            templates, profile.department, profile.designation, cycle.template_overrides
        )
        if not in_scope(cycle, profile, template):
            continue
        count += 1
        user = users.get(profile.user_id)
        ref = PersonRef(user_id=profile.user_id, name=user.name if user else "")
        if primary_link(links.get(profile.id, [])) is None:
            no_manager.append(ref)
        if template is None:
            no_template.append(ref)
        if user is not None:
            person = Person(user.id, user.name, user.email, user.github_username)
            found = possible_duplicates(person, loose)
            if found:
                maybe = [PersonRef(user_id=a.user_id, name=a.name) for a in found]
                identity.append(IdentityFlag(user_id=ref.user_id, name=ref.name, maybe=maybe))
    note = await _ai_note(db, cycle)
    return Readiness(
        drafting=DraftingMode.MANUAL if note else DraftingMode.AI,
        ai_note=note,
        in_scope=count,
        no_primary_manager=sorted(no_manager, key=lambda r: r.name.lower()),
        no_template=sorted(no_template, key=lambda r: r.name.lower()),
        identity=sorted(identity, key=lambda r: r.name.lower()),
    )
