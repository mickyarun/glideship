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

"""Resolve who owns a BUD phase for one org, and what that owner may do.

Most phases have a fixed owner (``phase_roles.PHASE_ROLE_CHAIN``). The
ones listed in ``ORG_CONFIGURABLE_PHASES`` depend on the org's settings,
so only those load the organization row.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import UserRole
from app.repositories.organization import OrganizationRepository
from app.schemas.settings import BUDStageSettings, UATOwner
from app.services.org_settings import get_bud_stage_settings
from app.services.phase_roles import ORG_CONFIGURABLE_PHASES, PHASE_ROLE_CHAIN, role_chains


async def org_bud_stage_settings(db: AsyncSession, org_id: uuid.UUID) -> BUDStageSettings:
    """Return the org's BUD stage settings (the shipped defaults if the org is missing)."""
    org = await OrganizationRepository(db).get_by_id(org_id)
    return get_bud_stage_settings(org.config if org else None)


async def uat_owner_is_qa(db: AsyncSession, org_id: uuid.UUID) -> bool:
    """Whether the org made QA the UAT owner, so QA may also move BUDs out of UAT."""
    return (await org_bud_stage_settings(db, org_id)).uat_owner is UATOwner.QA


async def role_chain_for_phase(
    db: AsyncSession, org_id: uuid.UUID, phase: str
) -> tuple[UserRole, ...]:
    """Return the ordered owner roles for ``phase`` in this org (empty if none)."""
    if phase not in ORG_CONFIGURABLE_PHASES:
        return PHASE_ROLE_CHAIN.get(phase, ())
    settings = await org_bud_stage_settings(db, org_id)
    return role_chains(settings.uat_owner).get(phase, ())
